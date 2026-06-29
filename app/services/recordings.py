"""Recordings retrieval (feature 6.6).

Resolves a user's lesson reference to a Drive recording folder via the lesson_map and
returns the playable parts as Drive view links (C4 - never downloaded). Honors empty
folders (C3) and gappy/odd part names (C2). All resolution goes through lesson_map; a
missing link is reported as "not linked yet" rather than guessed (C1).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.domain.lesson_map import LessonMap
from app.domain.models import RecordingPart
from app.services.drive import DriveService
from app.services.drive_parser import parse_recording_parts
from app.services.schedule import YamlScheduleService


@dataclass(frozen=True)
class RecordingResult:
    """Outcome of resolving a recording request for one lesson."""

    label: str
    folder_id: str | None
    parts: list[RecordingPart] = field(default_factory=list)

    @property
    def linked(self) -> bool:
        """True if a recording folder is mapped for this lesson."""
        return self.folder_id is not None

    @property
    def empty(self) -> bool:
        """True if the folder exists but has no playable files (C3)."""
        return self.folder_id is not None and not self.parts


class RecordingsService:
    """Resolves and lists lesson recordings as Drive links."""

    def __init__(
        self,
        drive: DriveService,
        lesson_map: LessonMap,
        schedule: YamlScheduleService,
    ) -> None:
        self._drive = drive
        self._map = lesson_map
        self._schedule = schedule

    async def _parts_in(self, folder_id: str) -> list[RecordingPart]:
        children = await self._drive.list_children(folder_id)
        return parse_recording_parts(children)

    async def by_alex_label(self, label: int) -> RecordingResult:
        """Recordings for one of Alex's 'Lesson N' folders."""
        folder_id = self._map.recording_folder_by_label(label)
        if folder_id is None:
            return RecordingResult(label=f"Lesson {label}", folder_id=None)
        parts = await self._parts_in(folder_id)
        return RecordingResult(label=f"Lesson {label}", folder_id=folder_id, parts=parts)

    async def for_session_date(
        self, session_date: str, *, label: str | None = None
    ) -> RecordingResult:
        """Recordings for a website session date, resolved via lesson_map."""
        folder_id = self._map.recording_folder_for_session(session_date)
        display = label or session_date
        if folder_id is None:
            return RecordingResult(label=display, folder_id=None)
        parts = await self._parts_in(folder_id)
        return RecordingResult(label=display, folder_id=folder_id, parts=parts)

    async def last(self) -> RecordingResult | None:
        """Most recent past technical session with a linked, non-empty recording."""
        today = self._schedule.today()
        past_technical = [
            s
            for s in reversed(self._schedule.all_sessions())
            if s.is_technical and s.date <= today
        ]
        for session in past_technical:
            result = await self.for_session_date(
                session.date.isoformat(), label=session.title
            )
            if result.linked and not result.empty:
                return result
        return None

    async def all_with_recordings(self) -> list[RecordingResult]:
        """All of Alex's known recording folders with their (possibly empty) parts."""
        results: list[RecordingResult] = []
        for label in sorted(self._map.recordings_by_alex_label):
            results.append(await self.by_alex_label(label))
        return results
