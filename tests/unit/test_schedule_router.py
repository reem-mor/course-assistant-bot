"""Unit tests for the deterministic keyword intent router (he/en)."""

from __future__ import annotations

import pytest
from app.bot.router import IntentName, Scope, route


@pytest.mark.parametrize(
    ("text", "scope"),
    [
        ("מתי השיעור הבא?", Scope.NEXT),
        ("השיעור הבא", Scope.NEXT),
        ("next lesson please", Scope.NEXT),
        ("what's next?", Scope.NEXT),
        ("whats next", Scope.NEXT),
        ("מה יש השבוע", Scope.THIS_WEEK),
        ("what's on this week", Scope.THIS_WEEK),
        ("לוז", Scope.FULL),
        ("מערכת שעות", Scope.FULL),
        ("show me the full schedule", Scope.FULL),
        ("schedule", Scope.FULL),
    ],
)
def test_schedule_scopes(text: str, scope: Scope) -> None:
    intent = route(text)
    assert intent is not None
    assert intent.name is IntentName.SCHEDULE
    assert intent.scope is scope


def test_next_wins_over_generic_schedule() -> None:
    # Contains both "next lesson" and "schedule"; NEXT has priority.
    intent = route("what is the next lesson in the schedule")
    assert intent is not None
    assert intent.scope is Scope.NEXT


@pytest.mark.parametrize("text", ["", "   ", "hello there", "תודה רבה", None])
def test_non_schedule_returns_none(text: str | None) -> None:
    assert route(text) is None


def test_summarize_intent() -> None:
    intent = route("summarize lesson 5")
    assert intent is not None
    assert intent.name is IntentName.SUMMARIZE
    assert intent.lesson_ref == "5"
    assert not intent.deep


def test_summarize_deep_from_recording() -> None:
    intent = route("summarize lesson 5 from the recording")
    assert intent is not None
    assert intent.name is IntentName.SUMMARIZE
    assert intent.deep


def test_summarize_hebrew() -> None:
    intent = route("סכם שיעור")
    assert intent is not None
    assert intent.name is IntentName.SUMMARIZE


def test_materials_intent() -> None:
    intent = route("recommended materials for docker")
    assert intent is not None
    assert intent.name is IntentName.MATERIALS
    assert intent.query is not None and "docker" in intent.query


def test_materials_hebrew() -> None:
    intent = route("חומרים מומלצים")
    assert intent is not None
    assert intent.name is IntentName.MATERIALS


def test_homework_submit_intent() -> None:
    intent = route("draft submission")
    assert intent is not None
    assert intent.name is IntentName.HOMEWORK_SUBMIT
