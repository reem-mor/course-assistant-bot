"""Tests for the C8 academic-integrity guardrail."""

from __future__ import annotations

import pytest
from app.services.submission import looks_like_solve_request, scaffold_disclaimer


@pytest.mark.parametrize(
    "text",
    [
        "can you do my homework",
        "please solve the assignment for me",
        "write the solution for me",
        "תפתור לי את המטלה",
        "עשה לי את השיעורי בית",
    ],
)
def test_detects_solve_requests(text: str) -> None:
    assert looks_like_solve_request(text)


@pytest.mark.parametrize(
    "text",
    [
        "draft submission email",
        "summarize lesson 5",
        "what's the latest homework",
        "מתי השיעור הבא",
    ],
)
def test_ignores_non_solve(text: str) -> None:
    assert not looks_like_solve_request(text)


def test_disclaimer_is_labeled_scaffold() -> None:
    assert "starter scaffold" in scaffold_disclaimer("en")
    assert "שלד התחלתי" in scaffold_disclaimer("he")
