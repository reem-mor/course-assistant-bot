"""Schedule service.

Source of truth is ``data/schedule.yaml`` (Asia/Jerusalem). The live site is a
refresh/diff source only (Phase 5). All date math happens in Israel time (C6).

The service takes an injectable clock (``now_provider``) so week-boundary, "next", and
"course finished" logic is fully deterministic under test without freezing global time.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Protocol, runtime_checkable
from zoneinfo import ZoneInfo

import yaml

from app.domain.models import Course, Session, SessionStatus, SessionType

ISRAEL_TZ = ZoneInfo("Asia/Jerusalem")

# Repo-relative default location of the seeded schedule.
_DEFAULT_SCHEDULE_PATH = Path(__file__).resolve().parents[2] / "data" / "schedule.yaml"


def now_in_israel() -> datetime:
    """Return the current timezone-aware datetime in Asia/Jerusalem."""
    return datetime.now(tz=ISRAEL_TZ)


def week_window(reference: date) -> tuple[date, date]:
    """Return the (Sunday, Saturday) window containing ``reference``.

    The cohort weeks run Sunday-Saturday (Israel). Python's ``weekday()`` is Mon=0..Sun=6,
    so days since the most recent Sunday is ``(weekday + 1) % 7``.
    """
    days_since_sunday = (reference.weekday() + 1) % 7
    start = reference - timedelta(days=days_since_sunday)
    return start, start + timedelta(days=6)


@runtime_checkable
class ScheduleService(Protocol):
    """Read access to the seeded course schedule (typed ``Session`` objects)."""

    def next_session(self) -> Session | None: ...

    def sessions_this_week(self) -> list[Session]: ...

    def all_sessions(self) -> list[Session]: ...

    def sessions_grouped_by_week(self) -> list[tuple[int, list[Session]]]: ...

    def is_course_finished(self) -> bool: ...


class YamlScheduleService:
    """``ScheduleService`` backed by a YAML file, evaluated against an injected clock."""

    def __init__(
        self,
        course: Course,
        *,
        now_provider: Callable[[], datetime] = now_in_israel,
    ) -> None:
        self._course = course
        self._now = now_provider
        # Stable chronological order (by date, then start time) used everywhere.
        self._sorted: list[Session] = sorted(
            course.sessions, key=lambda s: (s.date, s.start_time)
        )

    @classmethod
    def from_yaml(
        cls,
        path: Path | str = _DEFAULT_SCHEDULE_PATH,
        *,
        now_provider: Callable[[], datetime] = now_in_israel,
    ) -> YamlScheduleService:
        """Load and validate the schedule from a YAML file."""
        raw = Path(path).read_text(encoding="utf-8")
        data = yaml.safe_load(raw)
        course_data = dict(data["course"])
        course_data["sessions"] = data["sessions"]
        course = Course.model_validate(course_data)
        return cls(course, now_provider=now_provider)

    @property
    def course(self) -> Course:
        """The loaded course metadata + sessions."""
        return self._course

    def today(self) -> date:
        """Today's date in Israel time."""
        return self._now().astimezone(ISRAEL_TZ).date()

    def all_sessions(self) -> list[Session]:
        """All sessions in chronological order."""
        return list(self._sorted)

    def next_session(self) -> Session | None:
        """The nearest session today or later, or None if the course is finished."""
        today = self.today()
        for session in self._sorted:
            if session.date >= today:
                return session
        return None

    def sessions_this_week(self) -> list[Session]:
        """Sessions within the current Sun-Sat window (Israel)."""
        start, end = week_window(self.today())
        return [s for s in self._sorted if start <= s.date <= end]

    def sessions_grouped_by_week(self) -> list[tuple[int, list[Session]]]:
        """All sessions grouped by their course ``week`` number, in order."""
        grouped: dict[int, list[Session]] = {}
        for session in self._sorted:
            grouped.setdefault(session.week, []).append(session)
        return sorted(grouped.items())

    def sessions_on(self, day: date) -> list[Session]:
        """All sessions occurring on a specific date (handles two-same-day)."""
        return [s for s in self._sorted if s.date == day]

    def is_holiday_today(self) -> bool:
        """True if any session today is a holiday."""
        return any(s.type is SessionType.HOLIDAY for s in self.sessions_on(self.today()))

    def is_course_finished(self) -> bool:
        """True if every session is in the past."""
        today = self.today()
        return all(s.date < today for s in self._sorted) if self._sorted else True

    def status_of(self, session: Session) -> SessionStatus:
        """Status of a session relative to the current week window and today."""
        start, end = week_window(self.today())
        return session.status_within(week_start=start, week_end=end, today=self.today())


@lru_cache(maxsize=1)
def get_schedule_service() -> YamlScheduleService:
    """Return a cached, default-configured schedule service (production wiring)."""
    return YamlScheduleService.from_yaml()
