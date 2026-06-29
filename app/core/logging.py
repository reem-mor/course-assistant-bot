"""Structured logging configuration.

Emits JSON logs in production (machine-parseable for shipping to a log backend) and
human-friendly console logs in development. A redaction processor guarantees that
``SecretStr`` values and obviously sensitive keys never reach the log output.
"""

from __future__ import annotations

import logging
import sys
from collections.abc import MutableMapping
from typing import Any

import structlog
from pydantic import SecretStr

# Keys whose values are scrubbed regardless of type, as a defense-in-depth measure.
_SENSITIVE_KEY_HINTS: tuple[str, ...] = (
    "token",
    "secret",
    "password",
    "passwd",
    "api_key",
    "apikey",
    "refresh_token",
    "authorization",
)

_REDACTED = "***redacted***"

EventDict = MutableMapping[str, Any]


def _redact_secrets(
    _logger: Any, _method_name: str, event_dict: EventDict
) -> EventDict:
    """Redact secret values from a log event before rendering.

    Any ``SecretStr`` is replaced, and any key matching a sensitive hint is masked.
    """
    for key, value in list(event_dict.items()):
        if isinstance(value, SecretStr):
            event_dict[key] = _REDACTED
            continue
        lowered = key.lower()
        if any(hint in lowered for hint in _SENSITIVE_KEY_HINTS):
            event_dict[key] = _REDACTED
    return event_dict


def configure_logging(*, level: str = "INFO", json_logs: bool = True) -> None:
    """Configure stdlib logging and structlog with a shared processor chain.

    Idempotent enough for repeated calls in tests; the last configuration wins.
    """
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, level.upper(), logging.INFO),
    )

    shared_processors: list[structlog.typing.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        _redact_secrets,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    renderer: structlog.typing.Processor = (
        structlog.processors.JSONRenderer()
        if json_logs
        else structlog.dev.ConsoleRenderer(colors=False)
    )

    structlog.configure(
        processors=[*shared_processors, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper(), logging.INFO)
        ),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Return a bound structlog logger, optionally namespaced by ``name``."""
    logger: structlog.stdlib.BoundLogger = structlog.get_logger(name)
    return logger
