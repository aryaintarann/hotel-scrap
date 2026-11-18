"""T-060: alerts go to Discord/Telegram when configured, otherwise only to the log."""

import json

import httpx
import respx

from hotelpilot.core.config import get_settings
from hotelpilot.notify import alert


async def test_without_targets_only_logs():
    with respx.mock(assert_all_called=False) as m:
        assert await alert("job_dead", "x") == []
        assert m.calls.call_count == 0


@respx.mock
async def test_discord_and_telegram(monkeypatch):
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.test/hook")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:abc")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "42")
    get_settings.cache_clear()
    d = respx.post("https://discord.test/hook").mock(return_value=httpx.Response(204))
    t = respx.post("https://api.telegram.org/bot123:abc/sendMessage").mock(return_value=httpx.Response(200))
    for kind in ("job_dead", "token_expiring", "buffer_low", "budget_80"):
        assert await alert(kind, "msg") == ["discord", "telegram"]
    assert "budget_80" in json.loads(d.calls[-1].request.content)["content"]
    assert json.loads(t.calls[-1].request.content)["chat_id"] == "42"


@respx.mock
async def test_delivery_failure_never_raises(monkeypatch):
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.test/hook")
    get_settings.cache_clear()
    respx.post("https://discord.test/hook").mock(return_value=httpx.Response(500))
    assert await alert("job_dead", "x") == []
