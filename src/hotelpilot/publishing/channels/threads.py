"""Threads channel (spec 010): container → status → publish, quota, token refresh. Dummy when no token."""

from __future__ import annotations

import asyncio
import hashlib
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from hotelpilot.core import db
from hotelpilot.core.config import get_settings
from hotelpilot.core.logging import log
from hotelpilot.core.security import decrypt, encrypt
from hotelpilot.publishing.channels.base import (
    THREADS_MAX,
    OutgoingPost,
    PublishResult,
    Quota,
    QuotaExceeded,
    threads_length,
)

TOKEN_LIFETIME = timedelta(days=60)


class ThreadsError(Exception):
    pass


# --- token storage (encrypted in social_accounts) ---------------------------------------------


async def ensure_account() -> tuple[str, str] | None:
    """Seed/replace the stored token from THREADS_ACCESS_TOKEN when it changed. Returns (user_id, token)."""
    s = get_settings()
    if not s.threads_enabled:
        return None
    env_token = s.threads_access_token.get_secret_value()
    env_sha = hashlib.sha256(env_token.encode()).hexdigest()
    async with db.tx() as c:
        row = await db.one(
            c,
            "select token_enc from social_accounts where channel = 'threads' and external_user_id = :u",
            u=s.threads_user_id,
        )
        if row is None or await db.get_setting(c, "threads_env_token_sha") != env_sha:
            await db.exec(
                c,
                "insert into social_accounts(channel, external_user_id, token_enc, token_expires_at)"
                " values ('threads', :u, :t, :e) on conflict (channel, external_user_id)"
                " do update set token_enc = excluded.token_enc, token_expires_at = excluded.token_expires_at,"
                " active = true",
                u=s.threads_user_id,
                t=encrypt(env_token),
                e=datetime.now(UTC) + TOKEN_LIFETIME,
            )
            await db.set_setting(c, "threads_env_token_sha", env_sha)
            return s.threads_user_id, env_token
    return s.threads_user_id, decrypt(row["token_enc"])


async def save_token(user_id: str, token: str, expires_at: datetime) -> None:
    async with db.tx() as c:
        await db.exec(
            c,
            "update social_accounts set token_enc = :t, token_expires_at = :e"
            " where channel = 'threads' and external_user_id = :u",
            t=encrypt(token),
            e=expires_at,
            u=user_id,
        )


# --- channels ----------------------------------------------------------------------------------


class ThreadsChannel:
    key = "threads"

    def __init__(
        self,
        user_id: str,
        token: str,
        *,
        base_url: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
        poll_interval: float = 1.0,
        max_polls: int = 15,
    ) -> None:
        self.user_id, self.token = user_id, token
        self.base = (base_url or get_settings().threads_api_base).rstrip("/")
        self.transport = transport
        self.poll_interval, self.max_polls = poll_interval, max_polls

    async def _call(self, method: str, url: str, params: dict[str, Any]) -> dict[str, Any]:
        params = {**params, "access_token": self.token}
        path = url.replace(self.base, "")
        try:
            async with httpx.AsyncClient(timeout=30, transport=self.transport) as client:
                r = await client.request(method, url, params=params)
        except httpx.HTTPError as e:  # message may contain the URL with the token: only report the type
            raise ThreadsError(f"{method} {path}: {type(e).__name__}") from None
        if r.status_code >= 400:
            try:
                msg = r.json().get("error", {}).get("message", "")
            except ValueError:
                msg = r.text[:200]
            raise ThreadsError(f"{method} {path}: HTTP {r.status_code} {msg}".replace(self.token, "***"))
        return dict(r.json())

    async def quota(self) -> Quota:
        data = await self._call(
            "GET",
            f"{self.base}/{self.user_id}/threads_publishing_limit",
            {"fields": "quota_usage,config"},
        )
        item = (data.get("data") or [{}])[0]
        return Quota(
            used=int(item.get("quota_usage", 0)),
            total=int((item.get("config") or {}).get("quota_total", 250)),
        )

    async def publish(self, post: OutgoingPost) -> PublishResult:
        if threads_length(post.text) > THREADS_MAX:
            raise ValueError(f"post {post.id} exceeds {THREADS_MAX} bytes")
        q = await self.quota()
        if q.remaining <= 0:
            raise QuotaExceeded(f"threads_publishing_limit reached ({q.used}/{q.total})")
        container = await self._call(
            "POST",
            f"{self.base}/{self.user_id}/threads",
            {"media_type": "TEXT", "text": post.text, "topic_tag": post.topic_tag},
        )
        cid = container["id"]
        for _ in range(self.max_polls):
            st = await self._call("GET", f"{self.base}/{cid}", {"fields": "status,error_message"})
            status = st.get("status")
            if status == "FINISHED":
                break
            if status in ("ERROR", "EXPIRED"):
                raise ThreadsError(f"container {cid} {status}: {st.get('error_message', '')}")
            await asyncio.sleep(self.poll_interval)
        else:
            raise ThreadsError(f"container {cid} not FINISHED after {self.max_polls} polls")
        res = await self._call("POST", f"{self.base}/{self.user_id}/threads_publish", {"creation_id": cid})
        log.info("threads_published", post_id=post.id, external_id=res["id"], quota_used=q.used + 1)
        return PublishResult(external_id=str(res["id"]))

    async def refresh_credentials(self) -> None:
        root = self.base.rsplit("/v", 1)[0]
        data = await self._call("GET", f"{root}/refresh_access_token", {"grant_type": "th_refresh_token"})
        self.token = str(data["access_token"])
        expires = datetime.now(UTC) + timedelta(
            seconds=int(data.get("expires_in", TOKEN_LIFETIME.total_seconds()))
        )
        await save_token(self.user_id, self.token, expires)


class DummyChannel:
    """Used while THREADS_ACCESS_TOKEN is empty: the full flow runs, nothing leaves the machine."""

    key = "threads"

    async def publish(self, post: OutgoingPost) -> PublishResult:
        if threads_length(post.text) > THREADS_MAX:
            raise ValueError(f"post {post.id} exceeds {THREADS_MAX} bytes")
        log.info("threads_dummy_publish", post_id=post.id, text=post.text[:120])
        return PublishResult(external_id=f"dummy-{uuid.uuid4().hex[:10]}", dummy=True)

    async def quota(self) -> Quota:
        return Quota(used=0, total=250)

    async def refresh_credentials(self) -> None:
        return None


async def get_channel() -> ThreadsChannel | DummyChannel:
    acct = await ensure_account()
    if acct is None:
        return DummyChannel()
    return ThreadsChannel(*acct)


REFRESH_WHEN_LEFT = timedelta(days=15)


async def refresh_if_needed(now: datetime | None = None) -> str:
    """Daily job: refresh the long-lived token when < 15 days remain; alert on failure."""
    from hotelpilot.notify import alert

    now = now or datetime.now(UTC)
    acct = await ensure_account()
    if acct is None:
        return "dummy"
    async with db.tx() as c:
        expires = await db.val(
            c,
            "select token_expires_at from social_accounts"
            " where channel = 'threads' and external_user_id = :u",
            u=acct[0],
        )
    left = expires - now
    if left >= REFRESH_WHEN_LEFT:
        return "fresh"
    try:
        await ThreadsChannel(*acct).refresh_credentials()
    except ThreadsError as e:
        await alert("token_refresh_failed", f"Threads token refresh failed ({left.days} days left): {e}")
        return "failed"
    log.info("threads_token_refreshed", days_left_before=left.days)
    return "refreshed"
