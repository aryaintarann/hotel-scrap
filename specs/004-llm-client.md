# T-004/T-037 — Config, logging, LLM client (Shiteru AI), daily budget

**Config**: `core/config.py` (Pydantic Settings). Validated at start: Postgres URL, `JWT_SECRET` ≥ 32 chars,
`ADMIN_PASSWORD` non-empty; in `APP_ENV=prod` dev defaults are rejected and `ENCRYPTION_KEY` is required.

**Logging**: structlog JSON, `run_id` bound via contextvars, also sent to Shiteru as `x-correlation-id`.

**LLM client** (`core/llm.py`), the only LLM entry point. `complete_json(stage, system, user, schema, context)`:
- POST `{LLM_BASE_URL}/chat/completions`, `Authorization: Bearer {LLM_API_KEY}`, `model={LLM_MODEL}`.
- Retry: timeout / transport error / 429 / 5xx → exponential backoff with jitter, max `LLM_MAX_RETRIES`.
  402 (balance), 401/403 and other 4xx → fail immediately. Timeout `LLM_TIMEOUT_S`.
- Output: first balanced JSON in the text (footer-tolerant) → `schema.model_validate`. Invalid → re-ask with
  the validation error, at most 2 times, then `LLMOutputError`.
- Every call writes `run_logs` (tokens in/out, billed tokens, `cost_usd = billed × LLM_USD_PER_M_BILLED_TOKENS / 1e6`).
- Budget: before each call, today's (WITA) `sum(run_logs.cost_usd)` ≥ `settings.budget_daily_usd` → `BudgetExceeded`;
  ≥ 80 % → alert. Only generation calls the LLM, so publishing from the buffer is unaffected.
- No `LLM_API_KEY` → `MockLLM`: deterministic generators registered per schema, same validation, logged at $0.

**Acceptance**: tests/integration/test_llm.py (mocked HTTP via respx).
