"""Tests for i18n detection/translation and error fallback messaging."""

from __future__ import annotations

from app.core.errors import (
    ExternalServiceError,
    user_fallback_message,
)
from app.core.i18n import detect_language, t


def test_detect_hebrew() -> None:
    assert detect_language("מתי השיעור הבא") == "he"


def test_detect_english() -> None:
    assert detect_language("next lesson please") == "en"


def test_detect_empty_defaults_to_hebrew() -> None:
    assert detect_language("") == "he"
    assert detect_language(None) == "he"


def test_translate_known_key_both_languages() -> None:
    assert t("echo_prefix", "he") == "קיבלתי"
    assert t("echo_prefix", "en") == "You said"


def test_translate_unknown_key_returns_key() -> None:
    assert t("does_not_exist", "en") == "does_not_exist"


def test_fallback_messages_localized() -> None:
    assert "נסו שוב" in user_fallback_message("he")
    assert "try again" in user_fallback_message("en")


def test_external_service_error_carries_service_label() -> None:
    err = ExternalServiceError("boom", service="drive")
    assert err.service == "drive"
    assert "boom" in str(err)
