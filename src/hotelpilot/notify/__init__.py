"""Alerts to Discord/Telegram (spec 011). Without a configured target: log only."""

from __future__ import annotations

import httpx

from hotelpilot.core.config import get_settings
from hotelpilot.core.logging import log

ALERT_KINDS = {"job_dead", "token_expiring", "token_refresh_failed", "buffer_low", "budget_80", "slot_empty"}


async def alert(kind: str, message: str) -> list[str]:
    """Send an alert; returns the channels it was delivered to. Never raises."""
    s = get_settings()
    log.warning("alert", kind=kind, message=message)
    sent: list[str] = []
    text = f"[HotelPilot] {kind}: {message}"
    async with httpx.AsyncClient(timeout=10) as client:
        if s.discord_webhook_url.get_secret_value():
            try:
                r = await client.post(s.discord_webhook_url.get_secret_value(), json={"content": text[:1900]})
                r.raise_for_status()
                sent.append("discord")
            except httpx.HTTPError as e:
                log.error("alert_discord_failed", error=str(e))
        if s.telegram_bot_token.get_secret_value() and s.telegram_chat_id:
            try:
                url = f"https://api.telegram.org/bot{s.telegram_bot_token.get_secret_value()}/sendMessage"
                r = await client.post(url, json={"chat_id": s.telegram_chat_id, "text": text[:4000]})
                r.raise_for_status()
                sent.append("telegram")
            except httpx.HTTPError as e:
                log.error("alert_telegram_failed", error=type(e).__name__)  # URL contains the bot token
    return sent
