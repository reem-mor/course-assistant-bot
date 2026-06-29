"""Tests for the SubmissionDraft state machine."""

from __future__ import annotations

import pytest
from app.domain.models import DraftState, SubmissionDraft


def _ready_draft() -> SubmissionDraft:
    return SubmissionDraft(
        full_name="A", topic="T", date_ddmmyyyy="01/01/2026", work="W", tech="X"
    )


def test_missing_fields_reported() -> None:
    draft = SubmissionDraft(full_name="A")
    missing = draft.missing_fields()
    assert "topic" in missing
    assert "work" in missing
    assert "full_name" not in missing


def test_happy_path_transitions() -> None:
    draft = _ready_draft()
    assert draft.state is DraftState.DRAFTING
    draft.mark_preview()
    assert draft.state is DraftState.PREVIEW
    draft.confirm()
    assert draft.state is DraftState.CONFIRMED
    draft.mark_sent()
    assert draft.state is DraftState.SENT


def test_cannot_preview_when_incomplete() -> None:
    with pytest.raises(ValueError, match="missing"):
        SubmissionDraft(full_name="A").mark_preview()


def test_cannot_confirm_from_drafting() -> None:
    with pytest.raises(ValueError, match="cannot confirm"):
        _ready_draft().confirm()


def test_cannot_send_unconfirmed() -> None:
    draft = _ready_draft()
    draft.mark_preview()
    with pytest.raises(ValueError, match="cannot mark sent"):
        draft.mark_sent()


def test_cancel_then_no_send() -> None:
    draft = _ready_draft()
    draft.cancel()
    assert draft.state is DraftState.CANCELLED


def test_cannot_cancel_after_sent() -> None:
    draft = _ready_draft()
    draft.mark_preview()
    draft.confirm()
    draft.mark_sent()
    with pytest.raises(ValueError, match="already-sent"):
        draft.cancel()


def test_has_attachment_or_link() -> None:
    draft = _ready_draft()
    assert not draft.has_attachment_or_link
    draft.github_link = "https://github.com/x"
    assert draft.has_attachment_or_link
