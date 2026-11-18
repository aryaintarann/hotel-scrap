"""T-050: jobs queue — SKIP LOCKED, idempotency, retry 1→5→15 min, dead-letter + alert."""

import asyncio
from datetime import timedelta

from hotelpilot.core import db
from hotelpilot.publishing import queue


async def test_idempotency_key_dedupes(conn_db):
    a = await queue.enqueue("publish_social", {"x": 1}, idempotency_key="threads:2026-11-18T10:00")
    b = await queue.enqueue("publish_social", {"x": 2}, idempotency_key="threads:2026-11-18T10:00")
    assert a is not None and b is None
    async with db.tx() as c:
        assert await db.val(c, "select count(*) from jobs") == 1


async def test_two_workers_never_take_same_job(conn_db):
    for i in range(20):
        await queue.enqueue("noop", {"i": i})
    seen: list[str] = []

    async def worker(name: str) -> None:
        while (job := await queue.claim(name)) is not None:
            seen.append(job["id"])
            await asyncio.sleep(0)
            await queue.complete(job["id"])

    await asyncio.gather(worker("w1"), worker("w2"), worker("w3"))
    assert len(seen) == 20 and len(set(seen)) == 20


async def test_retry_backoff_then_dead(conn_db, monkeypatch):
    alerts: list[str] = []

    async def fake_alert(kind: str, msg: str) -> list[str]:
        alerts.append(kind)
        return []

    monkeypatch.setattr(queue, "alert", fake_alert)
    jid = await queue.enqueue("boom", {})
    delays = []
    for _ in range(4):
        async with db.tx() as c:
            await db.exec(c, "update jobs set run_at = now() - interval '1 second' where id = :i", i=jid)
        job = await queue.claim("w")
        assert job is not None
        await queue.fail(job["id"], "kaput")
        async with db.tx() as c:
            row = await db.one(c, "select status, run_at - now() as d from jobs where id = :i", i=jid)
        assert row is not None
        delays.append((row["status"], row["d"]))
    assert [s for s, _ in delays] == ["failed", "failed", "failed", "dead"]
    for (_, d), minutes in zip(delays[:3], (1, 5, 15), strict=True):
        assert abs(d - timedelta(minutes=minutes)) < timedelta(seconds=5)
    assert alerts == ["job_dead"]
    assert await queue.claim("w") is None


async def test_run_worker_once_dispatches_handlers(conn_db):
    got = []

    async def handler(payload: dict) -> dict:
        got.append(payload["v"])
        return {"ok": True}

    async def bad(payload: dict) -> None:
        raise RuntimeError("nope")

    await queue.enqueue("good", {"v": 7})
    await queue.enqueue("bad", {})
    assert await queue.run_once("w", {"good": handler, "bad": bad}) is True
    assert await queue.run_once("w", {"good": handler, "bad": bad}) is True
    assert await queue.run_once("w", {"good": handler, "bad": bad}) is False
    async with db.tx() as c:
        rows = {r["type"]: r for r in await db.all(c, "select type, status, error, result from jobs")}
    assert got == [7]
    assert rows["good"]["status"] == "succeeded" and rows["good"]["result"] == {"ok": True}
    assert rows["bad"]["status"] == "failed" and "nope" in rows["bad"]["error"]


async def test_stale_running_jobs_are_released(conn_db):
    jid = await queue.enqueue("x", {})
    await queue.claim("w")
    async with db.tx() as c:
        await db.exec(c, "update jobs set locked_at = now() - interval '1 hour' where id = :i", i=jid)
    assert await queue.release_stale() == 1
    assert (await queue.claim("w2")) is not None
