"""Unit tests for schedule date logic, driven by a frozen injected clock."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime

from app.domain.models import Course, Session, SessionStatus, SessionType
from app.services.schedule import (
    ISRAEL_TZ,
    YamlScheduleService,
    week_window,
)


def clock(year: int, month: int, day: int, hour: int = 12) -> Callable[[], datetime]:
    """Return a now-provider frozen to a specific Israel-time instant."""
    return lambda: datetime(year, month, day, hour, tzinfo=ISRAEL_TZ)


def service(now: Callable[[], datetime]) -> YamlScheduleService:
    """Load the real seeded schedule with a frozen clock."""
    return YamlScheduleService.from_yaml(now_provider=now)


def test_week_window_is_sunday_to_saturday() -> None:
    # 2026-06-18 is a Thursday.
    start, end = week_window(date(2026, 6, 18))
    assert start == date(2026, 6, 14)  # Sunday
    assert end == date(2026, 6, 20)  # Saturday


def test_week_window_on_sunday_starts_same_day() -> None:
    start, end = week_window(date(2026, 6, 14))
    assert start == date(2026, 6, 14)
    assert end == date(2026, 6, 20)


def test_week_window_on_saturday_keeps_window() -> None:
    start, end = week_window(date(2026, 6, 20))
    assert start == date(2026, 6, 14)
    assert end == date(2026, 6, 20)


def test_next_session_picks_nearest_upcoming() -> None:
    svc = service(clock(2026, 6, 16))  # Tuesday, between sessions
    nxt = svc.next_session()
    assert nxt is not None
    assert nxt.date == date(2026, 6, 17)
    assert "N8N deep dive" in nxt.title


def test_next_session_includes_today() -> None:
    svc = service(clock(2026, 6, 18))  # a Thursday session day
    nxt = svc.next_session()
    assert nxt is not None
    assert nxt.date == date(2026, 6, 18)


def test_course_finished_after_end() -> None:
    svc = service(clock(2026, 8, 1))
    assert svc.is_course_finished()
    assert svc.next_session() is None


def test_course_not_finished_during() -> None:
    svc = service(clock(2026, 6, 18))
    assert not svc.is_course_finished()


def test_this_week_window_contents() -> None:
    svc = service(clock(2026, 6, 18))
    dates = {s.date for s in svc.sessions_this_week()}
    assert dates == {date(2026, 6, 14), date(2026, 6, 17), date(2026, 6, 18)}


def test_this_week_next_window_shifts() -> None:
    svc = service(clock(2026, 6, 21))  # next Sunday
    dates = {s.date for s in svc.sessions_this_week()}
    assert dates == {date(2026, 6, 21), date(2026, 6, 24), date(2026, 6, 25)}


def test_holiday_today_detected() -> None:
    svc = service(clock(2026, 5, 21))  # Shavuot eve holiday
    assert svc.is_holiday_today()


def test_no_holiday_on_regular_day() -> None:
    svc = service(clock(2026, 6, 18))
    assert not svc.is_holiday_today()


def test_grouped_by_week_covers_all_weeks() -> None:
    svc = service(clock(2026, 6, 18))
    grouped = svc.sessions_grouped_by_week()
    week_numbers = [w for w, _ in grouped]
    assert week_numbers == list(range(1, 15))
    week1 = dict(grouped)[1]
    assert len(week1) == 3


def test_status_of_done_and_upcoming() -> None:
    svc = service(clock(2026, 6, 18))
    first = svc.all_sessions()[0]  # 2026-04-26, long past
    last = svc.all_sessions()[-1]  # 2026-07-30, future
    assert svc.status_of(first) is SessionStatus.DONE
    assert svc.status_of(last) is SessionStatus.UPCOMING


def test_two_sessions_same_day() -> None:
    # The real schedule has no same-day pair; verify the helper handles a synthetic one.
    same_day = date(2026, 6, 30)
    course = Course(
        name="t",
        start=date(2026, 6, 1),
        end=date(2026, 7, 1),
        timezone="Asia/Jerusalem",
        sessions=[
            Session(
                week=1, date=same_day, day="Tue", time="09:00-12:00",
                title="Morning", instructor="Alex", type=SessionType.TECHNICAL,
            ),
            Session(
                week=1, date=same_day, day="Tue", time="13:00-15:00",
                title="Afternoon", instructor="Sagy", type=SessionType.WORKSHOP,
            ),
        ],
    )
    svc = YamlScheduleService(course, now_provider=clock(2026, 6, 30))
    on_day = svc.sessions_on(same_day)
    assert len(on_day) == 2
    assert [s.title for s in on_day] == ["Morning", "Afternoon"]
