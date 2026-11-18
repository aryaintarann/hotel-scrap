"""T-052: token with < 15 days left is refreshed; failure alerts."""

from datetime import UTC, datetime, timedelta

import httpx
import respx

from hotelpilot.core import db
from hotelpilot.core.config import get_settings
from hotelpilot.core.security import decrypt
from hotelpilot.publishing.channels import threads


async def _setup(monkeypatch, days_left: int) -> None:
    monkeypatch.setenv("THREADS_ACCESS_TOKEN", "old-token")
    monkeypatch.setenv("THREADS_USER_ID", "u1")
    get_settings.cache_clear()
    await threads.ensure_account()
    async with db.tx() as c:
        await db.exec(
            c,
            "update social_accounts set token_expires_at = :e",
            e=datetime.now(UTC) + timedelta(days=days_left),
        )


@respx.mock
async def test_refreshes_when_under_15_days(conn_db, monkeypatch):
    await _setup(monkeypatch, 10)
    route = respx.get("https://graph.threads.net/refresh_access_token").mock(
        return_value=httpx.Response(200, json={"access_token": "new-token", "expires_in": 5184000})
    )
    assert await threads.refresh_if_needed() == "refreshed"
    assert route.calls[0].request.url.params["grant_type"] == "th_refresh_token"
    async with db.tx() as c:
        row = await db.one(c, "select token_enc, token_expires_at from social_accounts")
    assert row is not None and decrypt(row["token_enc"]) == "new-token"
    assert row["token_expires_at"] > datetime.now(UTC) + timedelta(days=59)
    # the stale env token must not overwrite the refreshed one
    acct = await threads.ensure_account()
    assert acct == ("u1", "new-token")


@respx.mock
async def test_fresh_token_untouched(conn_db, monkeypatch):
    await _setup(monkeypatch, 40)
    assert await threads.refresh_if_needed() == "fresh"


@respx.mock
async def test_failure_alerts(conn_db, monkeypatch):
    await _setup(monkeypatch, 3)
    respx.get("https://graph.threads.net/refresh_access_token").mock(
        return_value=httpx.Response(400, json={})
    )
    sent = []

    async def fake_alert(kind, msg):
        sent.append(kind)
        return []

    monkeypatch.setattr("hotelpilot.notify.alert", fake_alert)
    assert await threads.refresh_if_needed() == "failed"
    assert sent == ["token_refresh_failed"]


async def test_dummy_mode_noop(conn_db):
    assert await threads.refresh_if_needed() == "dummy"
