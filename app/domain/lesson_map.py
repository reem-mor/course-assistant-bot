"""The lesson_map mapping layer (C1).

Resolves a website session (keyed by ISO date) to concrete Drive folders. There is no
implicit 1:1 mapping between website sessions and Alex's "Lesson N" Drive folders, so
every link is explicit. A missing link resolves to None and the bot says "not linked
yet" rather than guessing.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class SessionLink(BaseModel):
    """A confirmed link from a website session to Alex's Drive 'Lesson N' folders."""

    model_config = ConfigDict(frozen=True)

    recording_alex_label: int | None = None
    presentation_alex_label: int | None = None


class LessonRoots(BaseModel):
    """Stable top-level Drive anchors."""

    model_config = ConfigDict(frozen=True)

    course_folder: str
    recordings_folder: str
    presentations_folder: str
    hw_procedure_doc: str


class LessonMap(BaseModel):
    """The full mapping: roots, known recording folders, and confirmed session links."""

    roots: LessonRoots
    recordings_by_alex_label: dict[int, str] = Field(default_factory=dict)
    session_links: dict[str, SessionLink] = Field(default_factory=dict)

    def link_for(self, session_date: str) -> SessionLink | None:
        """Return the confirmed link for a session date, or None if unmapped."""
        return self.session_links.get(session_date)

    def recording_folder_for_session(self, session_date: str) -> str | None:
        """Resolve a session's recording folder id, or None if not linked/known."""
        link = self.session_links.get(session_date)
        if link is None or link.recording_alex_label is None:
            return None
        return self.recordings_by_alex_label.get(link.recording_alex_label)

    def recording_folder_by_label(self, alex_label: int) -> str | None:
        """Resolve a recording folder id directly by Alex's label."""
        return self.recordings_by_alex_label.get(alex_label)

    def presentation_label_for_session(self, session_date: str) -> int | None:
        """Return the presentation 'Lesson N' label linked to a session, if any."""
        link = self.session_links.get(session_date)
        return link.presentation_alex_label if link else None

    def linked_recording_sessions(self) -> list[str]:
        """All session dates that have a recording link, sorted."""
        return sorted(
            date
            for date, link in self.session_links.items()
            if link.recording_alex_label is not None
        )
