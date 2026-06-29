"""Tests that the logging redaction processor scrubs secrets."""

from __future__ import annotations

from app.core.logging import _redact_secrets, configure_logging, get_logger
from pydantic import SecretStr


def test_secretstr_value_is_redacted() -> None:
    event = {"event": "login", "token": SecretStr("hunter2")}
    out = _redact_secrets(None, "info", event)
    assert out["token"] == "***redacted***"
    assert "hunter2" not in str(out)


def test_sensitive_key_is_redacted_even_as_plain_string() -> None:
    event = {"event": "call", "api_key": "plain-value", "user": "alex"}
    out = _redact_secrets(None, "info", event)
    assert out["api_key"] == "***redacted***"
    assert out["user"] == "alex"


def test_non_sensitive_values_pass_through() -> None:
    event = {"event": "ok", "count": 3, "name": "lesson"}
    out = _redact_secrets(None, "info", event)
    assert out == {"event": "ok", "count": 3, "name": "lesson"}


def test_configure_logging_is_callable_and_returns_logger() -> None:
    configure_logging(level="DEBUG", json_logs=True)
    log = get_logger("test")
    assert log is not None
