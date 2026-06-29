"""Tests for typed settings: defaults, admin parsing, secret handling."""

from __future__ import annotations

import pytest
from app.core.settings import Environment, RunMode, Settings
from pydantic import SecretStr


def test_defaults_are_safe() -> None:
    s = Settings()
    assert s.environment is Environment.DEVELOPMENT
    assert s.run_mode is RunMode.POLLING
    assert s.health_port == 8080
    assert s.admin_telegram_ids == ()
    assert s.telegram_bot_token is None


def test_admin_ids_parsed_from_comma_string() -> None:
    s = Settings(admin_telegram_ids="111, 222 ,333")  # type: ignore[arg-type]
    assert s.admin_telegram_ids == (111, 222, 333)
    assert s.is_admin(222)
    assert not s.is_admin(444)


def test_admin_ids_empty_string_is_empty_tuple() -> None:
    s = Settings(admin_telegram_ids="")  # type: ignore[arg-type]
    assert s.admin_telegram_ids == ()


def test_owner_is_implicitly_admin() -> None:
    s = Settings(owner_telegram_ids="10", admin_telegram_ids="20")  # type: ignore[arg-type]
    assert s.is_owner(10)
    assert s.is_admin(10)  # owner implicitly admin
    assert s.is_admin(20)
    assert not s.is_owner(20)


def test_non_owner_non_admin_is_student() -> None:
    s = Settings(owner_telegram_ids="10", admin_telegram_ids="20")  # type: ignore[arg-type]
    assert not s.is_owner(99)
    assert not s.is_admin(99)


def test_require_token_raises_when_missing() -> None:
    s = Settings()
    with pytest.raises(RuntimeError, match="TELEGRAM_BOT_TOKEN"):
        s.require_telegram_token()


def test_require_token_returns_value() -> None:
    s = Settings(telegram_bot_token="abc123")  # type: ignore[arg-type]
    assert s.require_telegram_token() == "abc123"


def test_secret_not_exposed_in_repr() -> None:
    s = Settings(telegram_bot_token="topsecret")  # type: ignore[arg-type]
    assert isinstance(s.telegram_bot_token, SecretStr)
    assert "topsecret" not in repr(s)
    assert "topsecret" not in str(s)


def test_is_production_flag() -> None:
    assert Settings(environment="production").is_production  # type: ignore[arg-type]
    assert not Settings(environment="development").is_production  # type: ignore[arg-type]
