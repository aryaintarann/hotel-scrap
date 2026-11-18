import pytest
from pydantic import ValidationError

from hotelpilot.core.config import DEV_JWT_SECRET, Settings


def test_defaults_are_mock_modes():
    s = Settings()
    assert s.llm_enabled is False
    assert s.threads_enabled is False
    assert len(s.aes_key()) == 32


def test_short_jwt_secret_rejected():
    with pytest.raises(ValidationError):
        Settings(jwt_secret="short")


def test_prod_rejects_dev_defaults():
    with pytest.raises(ValidationError):
        Settings(app_env="prod", jwt_secret=DEV_JWT_SECRET)


def test_non_postgres_url_rejected():
    with pytest.raises(ValidationError):
        Settings(database_url="sqlite:///x.db")
