"""T-051: Threads contract against mocked Graph responses; token encrypted at rest; dummy without token."""

import httpx
import pytest
import respx

from hotelpilot.core import db
from hotelpilot.core.config import get_settings
from hotelpilot.publishing.channels.base import OutgoingPost, QuotaExceeded, fit_threads, threads_length
from hotelpilot.publishing.channels.threads import DummyChannel, ThreadsChannel, ThreadsError, get_channel

B = "https://graph.threads.net/v1.0"
POST = OutgoingPost(id="p1", text="Halo Bali #AIassisted", topic_tag="BaliHotels")


def _limit(used: int = 3) -> httpx.Response:
    return httpx.Response(200, json={"data": [{"quota_usage": used, "config": {"quota_total": 250}}]})


@respx.mock
async def test_two_step_publish_flow():
    respx.get(f"{B}/u1/threads_publishing_limit").mock(return_value=_limit())
    create = respx.post(f"{B}/u1/threads").mock(return_value=httpx.Response(200, json={"id": "c9"}))
    respx.get(f"{B}/c9").mock(
        side_effect=[
            httpx.Response(200, json={"status": "IN_PROGRESS"}),
            httpx.Response(200, json={"status": "FINISHED"}),
        ]
    )
    pub = respx.post(f"{B}/u1/threads_publish").mock(return_value=httpx.Response(200, json={"id": "m77"}))
    ch = ThreadsChannel("u1", "tok-secret", poll_interval=0)
    res = await ch.publish(POST)
    assert res.external_id == "m77" and not res.dummy
    q = create.calls[0].request.url.params
    assert (q["media_type"], q["text"], q["topic_tag"]) == ("TEXT", POST.text, "BaliHotels")
    assert pub.calls[0].request.url.params["creation_id"] == "c9"


@respx.mock
async def test_quota_exhausted_blocks_publish():
    respx.get(f"{B}/u1/threads_publishing_limit").mock(return_value=_limit(250))
    with pytest.raises(QuotaExceeded):
        await ThreadsChannel("u1", "t", poll_interval=0).publish(POST)


@respx.mock
async def test_container_error_and_no_token_leak():
    respx.get(f"{B}/u1/threads_publishing_limit").mock(return_value=_limit())
    respx.post(f"{B}/u1/threads").mock(
        return_value=httpx.Response(400, json={"error": {"message": "bad tok-secret param"}})
    )
    with pytest.raises(ThreadsError) as ei:
        await ThreadsChannel("u1", "tok-secret", poll_interval=0).publish(POST)
    assert "tok-secret" not in str(ei.value)


async def test_length_is_byte_aware():
    emoji = "🌴" * 126  # 126 chars but 504 bytes
    assert threads_length(emoji) == 504
    with pytest.raises(ValueError):
        await DummyChannel().publish(OutgoingPost(id="x", text=emoji, topic_tag="t"))
    text = fit_threads("kata " * 200, " https://x.test/id/a #AIassisted")
    assert threads_length(text) <= 500 and text.endswith("#AIassisted")


async def test_dummy_without_token(conn_db):
    ch = await get_channel()
    assert isinstance(ch, DummyChannel)
    assert (await ch.publish(POST)).dummy


async def test_token_encrypted_at_rest(conn_db, monkeypatch):
    monkeypatch.setenv("THREADS_ACCESS_TOKEN", "THQ-plain-token")
    monkeypatch.setenv("THREADS_USER_ID", "u1")
    get_settings.cache_clear()
    ch = await get_channel()
    assert isinstance(ch, ThreadsChannel) and ch.token == "THQ-plain-token"
    async with db.tx() as c:
        enc = await db.val(c, "select token_enc from social_accounts where channel='threads'")
    assert "THQ-plain-token" not in enc
    ch2 = await get_channel()  # second call reads the stored (decrypted) token
    assert isinstance(ch2, ThreadsChannel) and ch2.token == "THQ-plain-token"
