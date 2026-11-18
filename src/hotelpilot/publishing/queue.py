"""Postgres job queue (spec 009): FOR UPDATE SKIP LOCKED, idempotency keys, retry 1→5→15 min, dead-letter."""

from __future__ import annotations

import json
import traceback
from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Any

from hotelpilot.core import db
from hotelpilot.core.logging import log, new_run_id
from hotelpilot.notify import alert

BACKOFF_MINUTES = (1, 5, 15)
STALE_AFTER_MINUTES = 30
Handler = Callable[[dict[str, Any]], Awaitable[Any]]


async def enqueue(
    type: str,
    payload: dict[str, Any] | None = None,
    *,
    idempotency_key: str | None = None,
    run_at: datetime | None = None,
    max_attempts: int = 4,
) -> str | None:
    """Returns the new job id, or None when the idempotency key already exists."""
    async with db.tx() as c:
        jid = await db.val(
            c,
            "insert into jobs(type, payload, idempotency_key, run_at, max_attempts)"
            " values (:t, cast(:p as jsonb), :k, coalesce(:r, now()), :m)"
            " on conflict (idempotency_key) do nothing returning id",
            t=type,
            p=json.dumps(payload or {}, default=str),
            k=idempotency_key,
            r=run_at,
            m=max_attempts,
        )
    return str(jid) if jid else None


async def claim(worker: str) -> dict[str, Any] | None:
    async with db.tx() as c:
        row = await db.one(
            c,
            "update jobs set status = 'running', locked_at = now(), locked_by = :w, attempts = attempts + 1"
            " where id = (select id from jobs where status in ('pending','failed') and run_at <= now()"
            "             order by run_at for update skip locked limit 1)"
            " returning id, type, payload, attempts, max_attempts",
            w=worker,
        )
    if row:
        row["id"] = str(row["id"])
    return row


async def complete(job_id: str, result: Any = None) -> None:
    async with db.tx() as c:
        await db.exec(
            c,
            "update jobs set status = 'succeeded', locked_at = null, error = null,"
            " result = cast(:r as jsonb) where id = :i",
            i=job_id,
            r=json.dumps(result, default=str),
        )


async def fail(job_id: str, error: str) -> str:
    """Schedule a retry (1, 5, 15 min) or move to dead-letter. Returns the new status."""
    async with db.tx() as c:
        row = await db.one(c, "select type, attempts, max_attempts from jobs where id = :i", i=job_id)
        assert row is not None
        if row["attempts"] >= row["max_attempts"]:
            await db.exec(
                c,
                "update jobs set status = 'dead', locked_at = null, error = :e where id = :i",
                i=job_id,
                e=error,
            )
            status = "dead"
        else:
            delay = BACKOFF_MINUTES[min(row["attempts"], len(BACKOFF_MINUTES)) - 1]
            await db.exec(
                c,
                "update jobs set status = 'failed', locked_at = null, error = :e,"
                " run_at = now() + make_interval(mins => :d) where id = :i",
                i=job_id,
                e=error,
                d=delay,
            )
            status = "failed"
    if status == "dead":
        await alert(
            "job_dead", f"job {row['type']} {job_id} dead after {row['attempts']} attempts: {error[:300]}"
        )
    return status


async def release_stale() -> int:
    async with db.tx() as c:
        return await db.exec(
            c,
            "update jobs set status = 'failed', locked_at = null, error = 'stale lock released'"
            " where status = 'running' and locked_at < now() - make_interval(mins => :m)",
            m=STALE_AFTER_MINUTES,
        )


async def run_once(worker: str, handlers: dict[str, Handler]) -> bool:
    """Process one due job. Returns False when the queue had nothing due."""
    job = await claim(worker)
    if job is None:
        return False
    new_run_id()
    handler = handlers.get(job["type"])
    log.info("job_start", job_id=job["id"], type=job["type"], attempt=job["attempts"])
    try:
        if handler is None:
            raise RuntimeError(f"no handler for job type {job['type']}")
        result = await handler(dict(job["payload"]))
    except Exception as e:  # noqa: BLE001 — every failure must reach retry/dead-letter
        log.error(
            "job_failed", job_id=job["id"], type=job["type"], error=str(e), tb=traceback.format_exc()[-1500:]
        )
        await fail(job["id"], f"{type(e).__name__}: {e}")
        return True
    await complete(job["id"], result)
    log.info("job_done", job_id=job["id"], type=job["type"])
    return True
