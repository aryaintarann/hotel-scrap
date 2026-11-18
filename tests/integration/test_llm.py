"""T-004 / T-037: Shiteru LLM client — retry+jitter, timeout, JSON-schema validation, cost logging, budget."""

import json

import httpx
import pytest
import respx
from pydantic import BaseModel, SecretStr

from hotelpilot.core import db
from hotelpilot.core.config import get_settings
from hotelpilot.core.llm import (
    BudgetExceeded,
    LLMError,
    LLMOutputError,
    MockLLM,
    ShiteruLLM,
    extract_json,
    get_llm,
    register_mock,
)

URL = "https://llm.test/v1/chat/completions"


class Greeting(BaseModel):
    text: str
    n: int


def _resp(content: str, billed: int = 3080, status: int = 200) -> httpx.Response:
    return httpx.Response(
        status,
        json={
            "choices": [{"message": {"role": "assistant", "content": content}}],
            "usage": {
                "prompt_tokens": 1200,
                "completion_tokens": 340,
                "total_tokens": 1540,
                "billing": {"billed_tokens": billed, "weighted_tokens": 1540, "multiplier": 2},
            },
        },
    )


def _client() -> ShiteruLLM:
    s = get_settings().model_copy(update={"llm_api_key": SecretStr("sk-test")})
    return ShiteruLLM(s, backoff_initial=0, backoff_max=0)


def test_extract_json_ignores_fences_and_footer():
    text = 'Here:\n```json\n{"text": "a {b}", "n": 1}\n```\n\nCost: 3080 tokens · kimi'
    assert extract_json(text) == {"text": "a {b}", "n": 1}
    with pytest.raises(ValueError):
        extract_json("no json here")


@respx.mock
async def test_success_logs_cost_and_tokens(conn_db):
    route = respx.post(URL).mock(return_value=_resp('{"text": "halo", "n": 2}'))
    out = await _client().complete_json(stage="t", system="s", user="u", schema=Greeting)
    assert out == Greeting(text="halo", n=2)
    req = route.calls[0].request
    assert req.headers["authorization"] == "Bearer sk-test"
    assert json.loads(req.content)["model"] == "kimi-k3.1-pro"
    async with db.tx() as c:
        row = await db.one(c, "select * from run_logs where stage = 't'")
    assert row is not None
    assert (row["llm_tokens_in"], row["llm_tokens_out"], row["llm_billed_tokens"]) == (1200, 340, 3080)
    assert float(row["cost_usd"]) == pytest.approx(3080 * 0.09 / 1e6)


@respx.mock
async def test_retries_429_and_timeouts_then_succeeds(conn_db):
    route = respx.post(URL).mock(
        side_effect=[
            httpx.Response(429, json={"error": {"code": "rate_limited"}}),
            httpx.ReadTimeout("slow"),
            httpx.Response(503, json={"error": {"code": "maintenance_mode"}}),
            _resp('{"text": "ok", "n": 1}'),
        ]
    )
    out = await _client().complete_json(stage="t", system="s", user="u", schema=Greeting)
    assert out.text == "ok" and route.call_count == 4


@respx.mock
async def test_402_not_retried(conn_db):
    route = respx.post(URL).mock(return_value=httpx.Response(402, json={"error": {"code": "x"}}))
    with pytest.raises(LLMError):
        await _client().complete_json(stage="t", system="s", user="u", schema=Greeting)
    assert route.call_count == 1


@respx.mock
async def test_gives_up_after_max_retries(conn_db):
    route = respx.post(URL).mock(return_value=httpx.Response(500))
    with pytest.raises(LLMError):
        await _client().complete_json(stage="t", system="s", user="u", schema=Greeting)
    assert route.call_count == get_settings().llm_max_retries + 1


@respx.mock
async def test_invalid_output_reasked_max_two_times(conn_db):
    route = respx.post(URL).mock(
        side_effect=[_resp("not json"), _resp('{"text": "x"}'), _resp('{"text": "x", "n": 3}')]
    )
    out = await _client().complete_json(stage="t", system="s", user="u", schema=Greeting)
    assert out.n == 3 and route.call_count == 3
    # the re-ask carries the validation error back to the model
    assert "invalid" in json.loads(route.calls[2].request.content)["messages"][-1]["content"]

    route.side_effect = [_resp("nope")] * 3
    with pytest.raises(LLMOutputError):
        await _client().complete_json(stage="t", system="s", user="u", schema=Greeting)


@respx.mock
async def test_budget_exceeded_blocks_call(conn_db):
    route = respx.post(URL).mock(return_value=_resp('{"text": "x", "n": 1}'))
    async with db.tx() as c:
        await db.set_setting(c, "budget_daily_usd", 0.01)
        await db.exec(c, "insert into run_logs(run_id, stage, status, cost_usd) values ('r','w','ok',0.02)")
    with pytest.raises(BudgetExceeded):
        await _client().complete_json(stage="t", system="s", user="u", schema=Greeting)
    assert route.call_count == 0


async def test_mock_llm_used_without_key_and_logged(conn_db):
    register_mock(Greeting, lambda ctx: {"text": f"hi {ctx['who']}", "n": 0})
    llm = get_llm()
    assert isinstance(llm, MockLLM)
    out = await llm.complete_json(stage="m", system="s", user="u", schema=Greeting, context={"who": "bali"})
    assert out.text == "hi bali"
    async with db.tx() as c:
        row = await db.one(c, "select * from run_logs where stage = 'm'")
    assert row is not None and float(row["cost_usd"]) == 0 and row["status"] == "ok"
