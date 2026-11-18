"""Application settings, loaded from environment / .env and validated at start (T-004)."""

from __future__ import annotations

import base64
import hashlib
from functools import lru_cache
from typing import Literal

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEV_JWT_SECRET = "dev-insecure-jwt-secret-change-me-0123456789"
DEV_ADMIN_PASSWORD = "admin"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: Literal["dev", "test", "prod"] = "dev"
    app_base_url: str = "http://localhost:8000"
    database_url: str = "postgresql+asyncpg://hotelpilot:hotelpilot@localhost:5432/hotelpilot"
    timezone: str = "Asia/Makassar"
    data_dir: str = "data"

    # Admin auth: Supabase-compatible HS256 JWT. Operator logs in with ADMIN_PASSWORD.
    jwt_secret: SecretStr = SecretStr(DEV_JWT_SECRET)
    admin_password: SecretStr = SecretStr(DEV_ADMIN_PASSWORD)
    encryption_key: SecretStr = SecretStr("")  # base64 32 bytes, AES-GCM for social tokens

    # LLM: Shiteru AI (OpenAI-compatible). Empty key -> mock LLM.
    llm_base_url: str = "https://shiteru.id/v1"
    llm_model: str = "kimi-k3.1-pro"
    llm_api_key: SecretStr = SecretStr("")
    llm_timeout_s: float = 180.0
    llm_max_retries: int = 4
    llm_max_tokens: int = 8000
    llm_usd_per_m_billed_tokens: float = 0.09  # Rp1.500 / 1M balance tokens ~ US$0.09
    llm_daily_budget_usd: float = 2.0  # default for settings.budget_daily_usd

    # Threads. Empty token -> dummy channel.
    threads_user_id: str = ""
    threads_access_token: SecretStr = SecretStr("")
    threads_api_base: str = "https://graph.threads.net/v1.0"

    # Blog webhook to an external frontend (optional)
    frontend_revalidate_url: str = ""
    webhook_secret: SecretStr = SecretStr("")

    # Alerts (optional)
    discord_webhook_url: SecretStr = SecretStr("")
    telegram_bot_token: SecretStr = SecretStr("")
    telegram_chat_id: str = ""

    # Ingestion
    ingest_mode: Literal["auto", "live", "fixture"] = "auto"
    overpass_url: str = "https://overpass-api.de/api/interpreter"
    overpass_min_interval_s: float = 5.0
    overture_release: str = ""  # empty -> latest from STAC catalog
    overture_stac_url: str = "https://stac.overturemaps.org/catalog.json"
    http_user_agent: str = "HotelPilot/0.3 (open-data hotel research bot)"

    @model_validator(mode="after")
    def _validate(self) -> Settings:
        if not self.database_url.startswith("postgresql"):
            raise ValueError("DATABASE_URL must be a postgresql URL")
        if len(self.jwt_secret.get_secret_value()) < 32:
            raise ValueError("JWT_SECRET must be at least 32 characters")
        if not self.admin_password.get_secret_value():
            raise ValueError("ADMIN_PASSWORD must not be empty")
        if self.app_env == "prod":
            if self.jwt_secret.get_secret_value() == DEV_JWT_SECRET:
                raise ValueError("JWT_SECRET still uses the dev default in prod")
            if self.admin_password.get_secret_value() == DEV_ADMIN_PASSWORD:
                raise ValueError("ADMIN_PASSWORD still uses the dev default in prod")
            if not self.encryption_key.get_secret_value():
                raise ValueError("ENCRYPTION_KEY is required in prod")
        key = self.encryption_key.get_secret_value()
        if key and len(base64.b64decode(key)) != 32:
            raise ValueError("ENCRYPTION_KEY must be base64 of 32 bytes")
        return self

    @property
    def llm_enabled(self) -> bool:
        return bool(self.llm_api_key.get_secret_value())

    @property
    def threads_enabled(self) -> bool:
        return bool(self.threads_access_token.get_secret_value() and self.threads_user_id)

    def aes_key(self) -> bytes:
        key = self.encryption_key.get_secret_value()
        if key:
            return base64.b64decode(key)
        # shortcut: dev/test derive the key from JWT_SECRET; prod requires ENCRYPTION_KEY (validated above)
        return hashlib.sha256(b"aes:" + self.jwt_secret.get_secret_value().encode()).digest()


@lru_cache
def get_settings() -> Settings:
    return Settings()
