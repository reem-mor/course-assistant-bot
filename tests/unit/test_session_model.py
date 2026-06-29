"""Unit tests for the Session domain model parsing and helpers."""

from __future__ import annotations

from datetime import date

from app.domain.models import Session, SessionType


def _row(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "week": 1,
        "date": "2026-04-29",
        "day": "Wed",
        "time": "09:00-15:15",
        "title": "AI engineering introduction and Python basics",
        "instructor": "Alex",
        "type": "technical",
    }
    base.update(overrides)
    return base


def test_parses_basic_row() -> None:
    s = Session.model_validate(_row())
    assert s.date == date(2026, 4, 29)
    assert s.type is SessionType.TECHNICAL
    assert s.is_technical
    assert s.start_time == "09:00"
    assert s.end_time == "15:15"
    assert s.has_named_instructor


def test_dash_instructor_is_empty() -> None:
    s = Session.model_validate(_row(instructor="—", type="milestone"))
    assert s.instructor == ""
    assert not s.has_named_instructor
    assert not s.is_technical


def test_hebrew_title_preserved() -> None:
    s = Session.model_validate(_row(title="Shavuot eve / ערב שבועות", type="holiday"))
    assert "ערב שבועות" in s.title
    assert s.type is SessionType.HOLIDAY


def test_time_without_range_has_no_end() -> None:
    s = Session.model_validate(_row(time="09:00"))
    assert s.start_time == "09:00"
    assert s.end_time is None


def test_session_is_frozen() -> None:
    s = Session.model_validate(_row())
    try:
        s.title = "changed"  # type: ignore[misc]
    except Exception as exc:  # pydantic raises on frozen mutation
        assert "frozen" in str(exc).lower() or "instance" in str(exc).lower()
    else:
        raise AssertionError("Session should be immutable")
