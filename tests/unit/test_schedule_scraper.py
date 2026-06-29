"""Tests for the schedule scraper parser + diff (offline, against a saved fixture)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from app.domain.models import Session, SessionType
from app.services.schedule_scraper import (
    diff_schedule,
    parse_schedule_text,
)

_FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "schedule_page.txt"


def _parsed() -> list:
    return parse_schedule_text(_FIXTURE.read_text(encoding="utf-8"))


def test_parses_expected_sessions() -> None:
    sessions = _parsed()
    by_date = {s.date: s for s in sessions}
    # Week 1 technical session with instructor.
    assert "2026-04-29" in by_date
    assert "AI engineering introduction" in by_date["2026-04-29"].title
    assert by_date["2026-04-29"].instructor == "Alex"
    assert by_date["2026-04-29"].type is SessionType.TECHNICAL


def test_parses_milestone_without_instructor() -> None:
    by_date = {s.date: s for s in _parsed()}
    opening = by_date["2026-04-26"]
    assert opening.type is SessionType.MILESTONE
    assert opening.instructor == ""


def test_parses_holiday() -> None:
    by_date = {s.date: s for s in _parsed()}
    holiday = by_date["2026-05-21"]
    assert holiday.type is SessionType.HOLIDAY
    assert "שבועות" in holiday.title


def test_parses_workshop() -> None:
    by_date = {s.date: s for s in _parsed()}
    workshop = by_date["2026-06-07"]
    assert workshop.type is SessionType.WORKSHOP
    assert workshop.instructor == "בר"


def test_diff_detects_changed_title() -> None:
    scraped = _parsed()
    current = [
        Session(
            week=1, date=date(2026, 4, 29), day="Wed", time="09:00-15:15",
            title="OLD TITLE", instructor="Alex", type=SessionType.TECHNICAL,
        )
    ]
    diff = diff_schedule(scraped, current)
    assert any(d[0] == "2026-04-29" for d in diff.changed)
    assert diff.has_changes


def test_diff_no_changes_when_matching() -> None:
    scraped = _parsed()
    # Build current sessions identical (by date+title) to the scraped ones.
    current = [
        Session(
            week=1, date=date.fromisoformat(s.date), day=s.day or "Wed",
            time=s.time or "09:00-15:15", title=s.title,
            instructor=s.instructor or "—", type=s.type,
        )
        for s in scraped
    ]
    diff = diff_schedule(scraped, current)
    assert diff.changed == []
