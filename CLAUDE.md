# CLAUDE.md — repo rules for HotelPilot

- Source of truth: `docs/PRD.md`, `docs/ARCHITECTURE.md`, `docs/TASKS.md` (the v0.2–v0.3 decision table wins), then `specs/NNN-*.md`. Deviations go to `docs/DECISIONS.md`.
- LLM provider: Shiteru AI (OpenAI-compatible) through the single client `src/hotelpilot/core/llm.py`, configured only by `LLM_BASE_URL`, `LLM_MODEL`, `LLM_API_KEY`. No other LLM SDK.
- The LLM only writes from the Fact Pack. Every factual sentence carries fact ids; QA rejects anything ungrounded.
- Every external integration has a mock/dummy mode that activates when its credential is empty, so the pipeline runs end to end without secrets.
- TDD: tests from acceptance criteria first. Gate: `make lint` (ruff, mypy) and `make test` (pytest, real Postgres via `make testdb`).
- One small commit per task; tick the task in `docs/TASKS.md` only after its tests pass.
- Never print or commit secrets. `.env`, `data/cache/`, `data/runtime/` stay untracked.
- Plain SQL via `hotelpilot.core.db` helpers; schema changes are new files in `supabase/migrations/`.
