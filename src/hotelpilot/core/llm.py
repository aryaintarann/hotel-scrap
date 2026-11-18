"""Single LLM client: Shiteru AI over its OpenAI-compatible API (LLM_BASE_URL / LLM_MODEL / LLM_API_KEY).

- retry with exponential backoff + jitter on timeouts, transport errors, 429 and 5xx (402/401/403 fail fast)
- per-request timeout
- output parsed as JSON and validated against a Pydantic schema; invalid output re-asked at most 2x
- every call logged to run_logs (tokens, billed tokens, USD cost); daily budget enforced before each call
Without LLM_API_KEY a deterministic MockLLM is used (generators registered per schema).
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from datetime import datetime
from typing import Any, Protocol, TypeVar
from zoneinfo import ZoneInfo

import httpx
from pydantic import BaseModel, ValidationError
from tenacity import AsyncRetrying, retry_if_exception, stop_after_attempt, wait_exponential_jitter

from hotelpilot.core import db
from hotelpilot.core.config import Settings, get_settings
from hotelpilot.core.logging import current_run_id, log

T = TypeVar("T", bound=BaseModel)
PARSE_RETRIES = 2


class LLMError(Exception):
    pass


class LLMOutputError(LLMError):
    pass


class BudgetExceeded(LLMError):
    pass


class LLMClient(Protocol):
    async def complete_json(
        self,
        *,
        stage: str,
        system: str,
        user: str,
        schema: type[T],
        context: dict[str, Any] | None = None,
        temperature: float = 0.4,
    ) -> T: ...


def extract_json(text: str) -> Any:
    """First balanced JSON object/array in text (tolerates ``` fences and provider footers)."""
    for start, ch in enumerate(text):
        if ch not in "{[":
            continue
        depth, in_str, esc = 0, False, False
        for i in range(start, len(text)):
            c = text[i]
            if in_str:
                esc = (not esc) and c == "\\"
                if c == '"' and not esc:
                    in_str = False
                continue
            if c == '"':
                in_str = True
            elif c in "{[":
                depth += 1
            elif c in "}]":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start : i + 1])
                    except json.JSONDecodeError:
                        break
    raise ValueError("no JSON object found in model output")


# --- cost & budget ---------------------------------------------------------------------------


async def spent_today_usd() -> float:
    tz = ZoneInfo(get_settings().timezone)
    day_start = datetime.now(tz).replace(hour=0, minute=0, second=0, microsecond=0)
    async with db.tx() as c:
        v = await db.val(
            c, "select coalesce(sum(cost_usd), 0) from run_logs where created_at >= :d", d=day_start
        )
    return float(v)


async def daily_budget_usd() -> float:
    async with db.tx() as c:
        v = await db.get_setting(c, "budget_daily_usd", get_settings().llm_daily_budget_usd)
    return float(v)


async def check_budget() -> None:
    spent, budget = await spent_today_usd(), await daily_budget_usd()
    if spent >= budget:
        raise BudgetExceeded(f"daily LLM budget reached: ${spent:.4f} of ${budget:.2f}")
    if spent >= 0.8 * budget:
        from hotelpilot.notify import alert

        await alert("budget_80", f"LLM spend ${spent:.4f} is above 80% of daily budget ${budget:.2f}")


async def record_run_log(
    stage: str,
    status: str,
    *,
    tokens_in: int = 0,
    tokens_out: int = 0,
    billed: int = 0,
    cost_usd: float = 0.0,
    duration_ms: int = 0,
    message: str | None = None,
    error: str | None = None,
) -> None:
    async with db.tx() as c:
        await db.exec(
            c,
            "insert into run_logs(run_id, stage, status, message, llm_tokens_in, llm_tokens_out,"
            " llm_billed_tokens, cost_usd, duration_ms, error)"
            " values (:r, :s, :st, :m, :ti, :to, :b, :cost, :d, :e)",
            r=current_run_id(),
            s=stage,
            st=status,
            m=message,
            ti=tokens_in,
            to=tokens_out,
            b=billed,
            cost=cost_usd,
            d=duration_ms,
            e=error,
        )


# --- Shiteru ---------------------------------------------------------------------------------


class _Retryable(Exception):
    pass


def _is_retryable(exc: BaseException) -> bool:
    return isinstance(exc, _Retryable | httpx.TimeoutException | httpx.TransportError)


def _schema_instructions(schema: type[BaseModel]) -> str:
    return (
        "Respond with ONE JSON object only, no prose, no markdown fences. "
        "It must validate against this JSON Schema:\n"
        + json.dumps(schema.model_json_schema(), ensure_ascii=False)
    )


class ShiteruLLM:
    def __init__(
        self,
        settings: Settings | None = None,
        *,
        backoff_initial: float = 1.0,
        backoff_max: float = 30.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.s = settings or get_settings()
        self.backoff_initial, self.backoff_max = backoff_initial, backoff_max
        self.transport = transport

    async def _post(self, messages: list[dict[str, str]], temperature: float) -> dict[str, Any]:
        body = {
            "model": self.s.llm_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": self.s.llm_max_tokens,
        }
        headers = {
            "Authorization": f"Bearer {self.s.llm_api_key.get_secret_value()}",
            "x-correlation-id": current_run_id(),
        }
        async with httpx.AsyncClient(
            base_url=self.s.llm_base_url, timeout=self.s.llm_timeout_s, transport=self.transport
        ) as client:
            async for attempt in AsyncRetrying(
                retry=retry_if_exception(_is_retryable),
                wait=wait_exponential_jitter(multiplier=self.backoff_initial, max=self.backoff_max),
                stop=stop_after_attempt(self.s.llm_max_retries + 1),
                reraise=True,
            ):
                with attempt:
                    r = await client.post("/chat/completions", json=body, headers=headers)
                    if r.status_code == 429 or r.status_code >= 500:
                        log.warning("llm_retryable_status", status=r.status_code, body=r.text[:200])
                        raise _Retryable(f"HTTP {r.status_code}")
                    if r.status_code >= 400:
                        raise LLMError(f"LLM HTTP {r.status_code}: {r.text[:300]}")
                    return dict(r.json())
        raise LLMError("unreachable")  # pragma: no cover

    async def complete_json(
        self,
        *,
        stage: str,
        system: str,
        user: str,
        schema: type[T],
        context: dict[str, Any] | None = None,
        temperature: float = 0.4,
    ) -> T:
        await check_budget()
        messages = [
            {"role": "system", "content": system + "\n\n" + _schema_instructions(schema)},
            {"role": "user", "content": user},
        ]
        last_err = ""
        for _ in range(PARSE_RETRIES + 1):
            t0 = time.monotonic()
            try:
                data = await self._post(messages, temperature)
            except (_Retryable, httpx.HTTPError) as e:
                await record_run_log(stage, "error", error=str(e), message=self.s.llm_model)
                raise LLMError(f"LLM unavailable after retries: {e}") from e
            except LLMError as e:
                await record_run_log(stage, "error", error=str(e), message=self.s.llm_model)
                raise
            usage = data.get("usage") or {}
            billed = int((usage.get("billing") or {}).get("billed_tokens") or usage.get("total_tokens") or 0)
            content = str(((data.get("choices") or [{}])[0].get("message") or {}).get("content") or "")
            try:
                result = schema.model_validate(extract_json(content))
                status, err = "ok", None
            except (ValueError, ValidationError) as e:
                result, status, err = None, "invalid_output", str(e)[:500]
            await record_run_log(
                stage,
                status,
                tokens_in=int(usage.get("prompt_tokens") or 0),
                tokens_out=int(usage.get("completion_tokens") or 0),
                billed=billed,
                cost_usd=billed * self.s.llm_usd_per_m_billed_tokens / 1e6,
                duration_ms=int((time.monotonic() - t0) * 1000),
                message=self.s.llm_model,
                error=err,
            )
            if result is not None:
                return result
            last_err = err or ""
            messages += [
                {"role": "assistant", "content": content[:4000]},
                {
                    "role": "user",
                    "content": f"Your output was invalid: {last_err}. Return only the corrected JSON object.",
                },
            ]
        raise LLMOutputError(f"invalid JSON after {PARSE_RETRIES} re-asks: {last_err}")


# --- Mock ------------------------------------------------------------------------------------

_MOCKS: dict[str, Callable[[dict[str, Any]], Any]] = {}


def register_mock(schema: type[BaseModel], fn: Callable[[dict[str, Any]], Any]) -> None:
    _MOCKS[schema.__name__] = fn


class MockLLM:
    """Deterministic stand-in: output built from `context` (the Fact Pack), validated like the real one."""

    async def complete_json(
        self,
        *,
        stage: str,
        system: str,
        user: str,
        schema: type[T],
        context: dict[str, Any] | None = None,
        temperature: float = 0.4,
    ) -> T:
        await check_budget()
        fn = _MOCKS.get(schema.__name__)
        if fn is None:
            raise LLMError(f"no mock registered for {schema.__name__}")
        result = schema.model_validate(fn(context or {}))
        await record_run_log(stage, "ok", message="mock")
        return result


def get_llm() -> LLMClient:
    s = get_settings()
    return ShiteruLLM(s) if s.llm_enabled else MockLLM()
