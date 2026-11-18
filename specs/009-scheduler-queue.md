# 009 — Job queue + 2-hour scheduler

## Queue (`publishing/queue.py`, T-050)
- `jobs` table; `claim()` = `UPDATE … WHERE id = (SELECT … FOR UPDATE SKIP LOCKED LIMIT 1)`, so concurrent workers never take the same job.
- `enqueue(type, payload, idempotency_key)` → `ON CONFLICT (idempotency_key) DO NOTHING`: re-enqueueing is a no-op.
- Failure: retry after 1 → 5 → 15 min (`max_attempts = 4` = 1 run + 3 retries), then `dead` + `job_dead` alert.
- `release_stale()` frees `running` jobs locked for > 30 min (crashed worker).
- `run_once(worker, handlers)` dispatches by `type`; every exception goes to retry/dead-letter.

**Acceptance**: tests/integration/test_queue.py (3 concurrent workers × 20 jobs → 20 unique; duplicate key → 1 job; 1/5/15 then dead).

## Scheduler — see section added in T-054.
