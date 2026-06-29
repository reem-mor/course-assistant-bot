"""Pydantic domain types.

Phase 1 introduces the schedule types: ``Session`` (a website calendar session) and
``Course`` (the seeded schedule wrapper). Later phases add ``Lesson``, ``RecordingPart``,
``MaterialFile``, ``SubmissionDraft``, etc.
"""

from __future__ import annotations

import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SessionType(StrEnum):
    """Category of a calendar session."""

    TECHNICAL = "technical"
    WORKSHOP = "workshop"
    MILESTONE = "milestone"
    HOLIDAY = "holiday"


class SessionStatus(StrEnum):
    """A session's status relative to the current week."""

    DONE = "done"
    THIS_WEEK = "this_week"
    UPCOMING = "upcoming"


class Session(BaseModel):
    """A single website calendar session.

    Mirrors a row in ``data/schedule.yaml``. ``date`` is coerced to a ``date`` object;
    ``time`` is kept as the raw ``"HH:MM-HH:MM"`` label with parsed convenience props.
    """

    model_config = ConfigDict(frozen=True)

    week: int
    date: datetime.date
    day: str
    time: str
    title: str
    instructor: str
    type: SessionType

    @field_validator("instructor")
    @classmethod
    def _normalize_instructor(cls, value: str) -> str:
        """Treat the placeholder dash as 'no named instructor'."""
        return "" if value.strip() in {"", "—", "-"} else value.strip()

    @property
    def start_time(self) -> str:
        """The session start time as ``HH:MM`` (best-effort from the label)."""
        return self.time.split("-", 1)[0].strip()

    @property
    def end_time(self) -> str | None:
        """The session end time as ``HH:MM``, or None if the label has no range."""
        parts = self.time.split("-", 1)
        return parts[1].strip() if len(parts) == 2 else None

    @property
    def is_technical(self) -> bool:
        """True for technical sessions (the ones that usually have Drive materials)."""
        return self.type is SessionType.TECHNICAL

    @property
    def has_named_instructor(self) -> bool:
        """True if a real instructor name is set (not the placeholder dash)."""
        return bool(self.instructor)

    def status_within(
        self, *, week_start: datetime.date, week_end: datetime.date, today: datetime.date
    ) -> SessionStatus:
        """Compute status relative to a Sun-Sat window and today's date."""
        if week_start <= self.date <= week_end:
            return SessionStatus.THIS_WEEK
        if self.date < today:
            return SessionStatus.DONE
        return SessionStatus.UPCOMING


class Course(BaseModel):
    """The seeded course schedule loaded from ``data/schedule.yaml``."""

    name: str
    start: datetime.date
    end: datetime.date
    timezone: str
    sessions: list[Session]


def drive_view_url(file_id: str) -> str:
    """Return a Google Drive view link for a file id (never a download link, C4)."""
    return f"https://drive.google.com/file/d/{file_id}/view"


def drive_folder_url(folder_id: str) -> str:
    """Return a Google Drive view link for a folder id."""
    return f"https://drive.google.com/drive/folders/{folder_id}"


class MaterialKind(StrEnum):
    """Classification of a Drive material file (C5: by mime + filename heuristics)."""

    SLIDES = "slides"
    HOMEWORK = "homework"
    CODE = "code"
    OTHER = "other"


class MaterialFile(BaseModel):
    """A non-recording file inside a presentation/materials folder."""

    model_config = ConfigDict(frozen=True)

    kind: MaterialKind
    name: str
    drive_file_id: str
    view_url: str
    modified_time: str | None = None


class RecordingPart(BaseModel):
    """A single recording video file (one 'part' of a lesson recording).

    ``part_index`` is None when no part number could be parsed from the name; such parts
    sort last and are presented transparently (C2).
    """

    model_config = ConfigDict(frozen=True)

    drive_file_id: str
    part_index: int | None
    name: str
    size: int | None
    view_url: str

    @property
    def label_number(self) -> str:
        """The part number as a display string, or '?' when unknown."""
        return str(self.part_index) if self.part_index is not None else "?"


class HomeworkAssignment(BaseModel):
    """A homework document resolved to a lesson."""

    model_config = ConfigDict(frozen=True)

    title: str
    lesson_key: str | None
    material: MaterialFile
    modified_time: str | None = None


class DraftState(StrEnum):
    """State machine for a homework submission draft (6.5)."""

    DRAFTING = "drafting"
    PREVIEW = "preview"
    CONFIRMED = "confirmed"
    SENT = "sent"
    CANCELLED = "cancelled"


class DraftAttachment(BaseModel):
    """A file the student attached to their submission (domain-level)."""

    model_config = ConfigDict(frozen=True)

    filename: str
    content: bytes
    mime_type: str


# Fields that must be filled before a draft can move to preview.
_REQUIRED_DRAFT_FIELDS: tuple[str, ...] = ("full_name", "topic", "date_ddmmyyyy", "work", "tech")


class SubmissionDraft(BaseModel):
    """A homework submission draft and its state machine.

    Transitions: drafting -> preview -> confirmed -> sent, with cancel from any non-sent
    state. Invalid transitions raise ``ValueError`` so the flow fails loudly in tests.
    """

    model_config = ConfigDict(validate_assignment=True)

    full_name: str | None = None
    topic: str | None = None
    date_ddmmyyyy: str | None = None
    work: str | None = None
    tech: str | None = None
    challenges: str | None = None
    attachments: list[DraftAttachment] = Field(default_factory=list)
    github_link: str | None = None
    state: DraftState = DraftState.DRAFTING

    def missing_fields(self) -> list[str]:
        """Return the names of required fields not yet provided."""
        return [f for f in _REQUIRED_DRAFT_FIELDS if not getattr(self, f)]

    @property
    def has_attachment_or_link(self) -> bool:
        """True if at least one attachment or a GitHub link is present."""
        return bool(self.attachments) or bool(self.github_link)

    def mark_preview(self) -> None:
        """Move drafting -> preview; requires all mandatory fields."""
        missing = self.missing_fields()
        if missing:
            raise ValueError(f"cannot preview, missing: {', '.join(missing)}")
        self.state = DraftState.PREVIEW

    def confirm(self) -> None:
        """Move preview -> confirmed."""
        if self.state is not DraftState.PREVIEW:
            raise ValueError(f"cannot confirm from state {self.state}")
        self.state = DraftState.CONFIRMED

    def mark_sent(self) -> None:
        """Move confirmed -> sent."""
        if self.state is not DraftState.CONFIRMED:
            raise ValueError(f"cannot mark sent from state {self.state}")
        self.state = DraftState.SENT

    def cancel(self) -> None:
        """Cancel the draft from any non-sent state."""
        if self.state is DraftState.SENT:
            raise ValueError("cannot cancel an already-sent draft")
        self.state = DraftState.CANCELLED
