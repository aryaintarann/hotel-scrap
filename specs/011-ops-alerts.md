# 011 — Notifier (Discord/Telegram)

`hotelpilot.notify.alert(kind, message)`; kinds: `job_dead`, `token_expiring`, `token_refresh_failed`,
`buffer_low`, `budget_80`, `slot_empty`. Sends to `DISCORD_WEBHOOK_URL` and/or Telegram
(`TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID`) when set; always logs. Never raises; the Telegram token is never logged.

Callers: queue dead-letter (T-050), token refresh (T-052), scheduler empty slot / replenish (T-054/T-055),
LLM budget > 80 % (T-037).

**Acceptance**: tests/unit/test_notify.py; trigger points are covered by their own task tests.
