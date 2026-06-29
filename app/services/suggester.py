"""lesson_map auto-suggester (brief 5.4).

A pure, best-effort proposal generator: it pairs Alex's existing "Lesson N" recording
folders with the course's technical website sessions in chronological order. It NEVER
applies links itself - the admin reviews proposals via ``/map suggest`` and confirms
each one. (The periodic worker job that runs this is Phase 5.)
"""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.lesson_map import LessonMap
from app.services.schedule import YamlScheduleService


@dataclass(frozen=True)
class MappingSuggestion:
    """A proposed link from a website session to one of Alex's recording folders."""

    session_date: str
    session_title: str
    recording_alex_label: int


def suggest_recording_links(
    schedule: YamlScheduleService, lesson_map: LessonMap
) -> list[MappingSuggestion]:
    """Propose session -> recording-folder links, skipping already-linked sessions.

    Best-effort chronological pairing of technical sessions to Alex's known recording
    folder labels. Folder ``createdTime`` proximity refinement is deferred to Phase 5.
    """
    technical = [s for s in schedule.all_sessions() if s.is_technical]
    labels = sorted(lesson_map.recordings_by_alex_label)
    suggestions: list[MappingSuggestion] = []
    for session, label in zip(technical, labels, strict=False):
        if session.date.isoformat() in lesson_map.session_links:
            continue
        suggestions.append(
            MappingSuggestion(
                session_date=session.date.isoformat(),
                session_title=session.title,
                recording_alex_label=label,
            )
        )
    return suggestions
