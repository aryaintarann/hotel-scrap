"""Test harness. Real Postgres (TEST_DATABASE_URL, see `make testdb`); every external service mocked."""

from __future__ import annotations

import os

# Force a hermetic environment: values from a developer's .env must never leak into tests.
TEST_DB = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:55432/postgres"
)
os.environ.update(
    {
        "APP_ENV": "test",
        "DATABASE_URL": TEST_DB,
        "JWT_SECRET": "test-secret-0123456789-0123456789-abcdef",
        "ADMIN_PASSWORD": "test-admin",
        "ENCRYPTION_KEY": "",
        "LLM_API_KEY": "",
        "LLM_BASE_URL": "https://llm.test/v1",
        "THREADS_ACCESS_TOKEN": "",
        "THREADS_USER_ID": "",
        "FRONTEND_REVALIDATE_URL": "",
        "WEBHOOK_SECRET": "",
        "DISCORD_WEBHOOK_URL": "",
        "TELEGRAM_BOT_TOKEN": "",
        "TELEGRAM_CHAT_ID": "",
        "INGEST_MODE": "fixture",
        "OVERPASS_MIN_INTERVAL_S": "0",
    }
)

import pytest  # noqa: E402

from hotelpilot.core import db  # noqa: E402
from hotelpilot.core.config import get_settings  # noqa: E402


@pytest.fixture(autouse=True)
def _settings_cache(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
async def conn_db():
    """Fresh schema per test, migrated."""
    from hotelpilot.core.migrate import reset_schema

    await db.dispose()
    await reset_schema()
    yield
    await db.dispose()
