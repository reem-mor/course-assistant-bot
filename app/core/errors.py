"""Shared error types and user-facing fallback messaging.

Internal failures should never leak stack traces or secrets to course participants.
Handlers catch exceptions, log them with full context, and reply with a localized,
friendly fallback produced here.
"""

from __future__ import annotations

from typing import Literal

Language = Literal["he", "en"]


class OzBotError(Exception):
    """Base class for all application-raised errors."""


class ConfigurationError(OzBotError):
    """Raised when required configuration is missing or invalid."""


class ExternalServiceError(OzBotError):
    """Raised when an external dependency (Drive, LLM, email, ASR) fails.

    Carries a ``service`` label so logs and metrics can attribute the failure.
    """

    def __init__(self, message: str, *, service: str) -> None:
        super().__init__(message)
        self.service = service


class NotFoundError(OzBotError):
    """Raised when a requested resource (lesson, recording, material) does not exist."""


_FALLBACK_MESSAGES: dict[Language, str] = {
    "he": (
        "מצטערים, משהו השתבש בעיבוד הבקשה. נסו שוב בעוד רגע, "
        "ואם זה חוזר על עצמו פנו לצוות הקורס."
    ),
    "en": (
        "Sorry, something went wrong while handling your request. Please try again "
        "in a moment, and contact the course staff if it keeps happening."
    ),
}


def user_fallback_message(language: Language = "he") -> str:
    """Return a friendly fallback message in the requested language.

    Defaults to Hebrew, matching the cohort's primary language.
    """
    return _FALLBACK_MESSAGES.get(language, _FALLBACK_MESSAGES["he"])
