"""Deterministic keyword intent router (he/en).

The fast-path the brief calls for: obvious requests are classified by keywords without
touching an LLM. Ambiguous input falls through (returns ``None``) and, from Phase 3
onward, will be handed to the LangGraph LLM router.

Phase 1 added the schedule intent; Phase 2 adds recording and latest-homework.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum


class IntentName(StrEnum):
    """Recognized intents. Extended in later phases."""

    SCHEDULE = "schedule"
    RECORDING = "recording"
    HOMEWORK_LATEST = "homework_latest"
    HOMEWORK_SUBMIT = "homework_submit"
    SUMMARIZE = "summarize"
    MATERIALS = "materials"


class Scope(StrEnum):
    """Scope qualifier for an intent."""

    NEXT = "next"
    THIS_WEEK = "this_week"
    FULL = "full"
    LAST = "last"
    SPECIFIC = "specific"
    ALL = "all"


@dataclass(frozen=True, slots=True)
class Intent:
    """A classified intent with optional scope, lesson reference, and deep flag."""

    name: IntentName
    scope: Scope | None = None
    lesson_ref: str | None = None
    deep: bool = False
    query: str | None = None


_SCHEDULE_KEYWORDS: tuple[tuple[Scope, tuple[str, ...]], ...] = (
    (
        Scope.NEXT,
        (
            "מתי השיעור הבא",
            "השיעור הבא",
            "השיעור הקרוב",
            "next lesson",
            "next class",
            "what's next",
            "whats next",
        ),
    ),
    (
        Scope.THIS_WEEK,
        ("מה יש השבוע", "מה השבוע", "השבוע", "this week"),
    ),
    (
        Scope.FULL,
        (
            "מערכת שעות",
            "מערכת השעות",
            "לוח זמנים",
            "כל השיעורים",
            "לוז",
            "full schedule",
            "schedule",
        ),
    ),
)

_RECORDING_TRIGGERS: tuple[str, ...] = (
    "הקלטה",
    "הקלטות",
    "recording",
    "recordings",
)
_RECORDING_ALL: tuple[str, ...] = ("all recordings", "כל ההקלטות", "all the recordings")
_RECORDING_LAST: tuple[str, ...] = (
    "last recording",
    "latest recording",
    "ההקלטה האחרונה",
    "השיעור האחרון",
    "הקלטה אחרונה",
)
_HOMEWORK_SUBMIT_KEYWORDS: tuple[str, ...] = (
    "כתוב לי טיוטה",
    "הגש שיעורי בית",
    "שלח מייל הגשה",
    "draft submission",
    "submit homework",
    "write submission email",
)
_HOMEWORK_KEYWORDS: tuple[str, ...] = (
    "שיעורי בית",
    "מה ההגשה",
    "המטלה האחרונה",
    "המטלה",
    "latest homework",
    "homework",
    "assignment",
    "hw",
)
_SUMMARIZE_KEYWORDS: tuple[str, ...] = (
    "סכם שיעור",
    "סיכום של השיעור",
    "סיכום שיעור",
    "תסכם",
    "summarize lesson",
    "lesson summary",
    "summarize",
    "summary of",
)
_DEEP_KEYWORDS: tuple[str, ...] = (
    "from the recording",
    "deep",
    "מההקלטה",
    "מהקלטה",
    "מתוך ההקלטה",
)
_MATERIALS_KEYWORDS: tuple[str, ...] = (
    "חומרים מומלצים",
    "מה כדאי ללמוד",
    "מקורות",
    "recommended materials",
    "resources",
    "what should i study",
)

_LESSON_REF_RE = re.compile(r"(?:lesson|שיעור)\s*#?\s*(\d+)", re.IGNORECASE)


def _normalize(text: str) -> str:
    """Lowercase and normalize apostrophes for tolerant English matching."""
    return text.lower().replace("\u2019", "'").strip()


def _match_schedule(normalized: str) -> Intent | None:
    for scope, keywords in _SCHEDULE_KEYWORDS:
        if any(keyword in normalized for keyword in keywords):
            return Intent(name=IntentName.SCHEDULE, scope=scope)
    return None


def _match_recording(normalized: str) -> Intent | None:
    if not any(trigger in normalized for trigger in _RECORDING_TRIGGERS):
        return None
    lesson_match = _LESSON_REF_RE.search(normalized)
    if lesson_match:
        return Intent(
            name=IntentName.RECORDING,
            scope=Scope.SPECIFIC,
            lesson_ref=lesson_match.group(1),
        )
    if any(kw in normalized for kw in _RECORDING_ALL):
        return Intent(name=IntentName.RECORDING, scope=Scope.ALL)
    if any(kw in normalized for kw in _RECORDING_LAST):
        return Intent(name=IntentName.RECORDING, scope=Scope.LAST)
    # Bare "recording" defaults to the most common ask: the last one.
    return Intent(name=IntentName.RECORDING, scope=Scope.LAST)


def _match_summarize(normalized: str) -> Intent | None:
    if not any(kw in normalized for kw in _SUMMARIZE_KEYWORDS):
        return None
    lesson_match = _LESSON_REF_RE.search(normalized)
    deep = any(kw in normalized for kw in _DEEP_KEYWORDS)
    return Intent(
        name=IntentName.SUMMARIZE,
        scope=Scope.SPECIFIC if lesson_match else None,
        lesson_ref=lesson_match.group(1) if lesson_match else None,
        deep=deep,
    )


def _match_materials(normalized: str) -> Intent | None:
    if any(kw in normalized for kw in _MATERIALS_KEYWORDS):
        return Intent(name=IntentName.MATERIALS, query=normalized)
    return None


def _match_homework_submit(normalized: str) -> Intent | None:
    if any(kw in normalized for kw in _HOMEWORK_SUBMIT_KEYWORDS):
        return Intent(name=IntentName.HOMEWORK_SUBMIT)
    return None


def _match_homework(normalized: str) -> Intent | None:
    if any(kw in normalized for kw in _HOMEWORK_KEYWORDS):
        return Intent(name=IntentName.HOMEWORK_LATEST)
    return None


def route(text: str | None) -> Intent | None:
    """Classify a message into an intent, or return None if no keyword matches."""
    if not text:
        return None
    normalized = _normalize(text)
    return (
        _match_schedule(normalized)
        or _match_summarize(normalized)
        or _match_materials(normalized)
        or _match_recording(normalized)
        or _match_homework_submit(normalized)
        or _match_homework(normalized)
    )
