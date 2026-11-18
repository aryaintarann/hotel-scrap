# 010 — Threads channel (TEXT only in MVP)

`publishing/channels/threads.py`
- `ThreadsChannel.publish(post)`: byte-aware length check (UTF-8 bytes ≤ 500) → `GET /{uid}/threads_publishing_limit`
  (refuse when exhausted) → `POST /{uid}/threads` (`media_type=TEXT`, `text`, `topic_tag`) → poll `GET /{container}?fields=status`
  until `FINISHED` (ERROR/EXPIRED/timeout → error) → `POST /{uid}/threads_publish creation_id=…` → external id.
- Errors never contain the access token (URL-bearing httpx messages are reduced to the exception type).
- `refresh_credentials()`: `GET /refresh_access_token?grant_type=th_refresh_token`, stores the new token + expiry.
- Token storage: `social_accounts.token_enc` (AES-GCM, key `ENCRYPTION_KEY`). `THREADS_ACCESS_TOKEN` seeds it; a changed
  env token (sha256 kept in `settings.threads_env_token_sha`) replaces the stored one, a refreshed token is never overwritten by a stale env value.
- `get_channel()` → `ThreadsChannel` when `THREADS_USER_ID` + `THREADS_ACCESS_TOKEN` are set, else `DummyChannel`
  (same validation, fake `dummy-…` id, nothing sent).
- Spike S-1: `scripts/spike_threads.py [--post]`.

**Acceptance**: tests/contract/test_threads.py (mocked Graph). Real-account posting: pending credentials (S-1).
