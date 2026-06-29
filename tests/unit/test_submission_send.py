"""Tests for finalize_and_send and email backend selection."""

from __future__ import annotations

from typing import Any

import pytest
from app.core.settings import Settings
from app.domain.models import DraftAttachment, DraftState, SubmissionDraft
from app.services.email import (
    EmailAttachment,
    GmailEmailService,
    SmtpEmailService,
    build_email_service,
)
from app.services.submission import finalize_and_send


class FakeEmailService:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.calls: list[dict[str, Any]] = []

    async def send(
        self,
        *,
        to: str,
        cc: str | None,
        subject: str,
        body: str,
        attachments: list[EmailAttachment],
    ) -> str:
        if self.fail:
            raise RuntimeError("smtp down")
        self.calls.append(
            {"to": to, "cc": cc, "subject": subject, "body": body, "attachments": attachments}
        )
        return "msg-123"


def _settings() -> Settings:
    return Settings(
        hw_to_email="kalex7878@gmail.com",
        hw_cc_email="sagy.galor@fursa.org.il,sagy.galor@portlandtrust.org.il",
    )


def _confirmed_draft() -> SubmissionDraft:
    draft = SubmissionDraft(
        full_name="John Doe", topic="Python Basics", date_ddmmyyyy="12/05/2026",
        work="W", tech="X",
        attachments=[DraftAttachment(filename="a.py", content=b"x", mime_type="text/x-python")],
    )
    draft.mark_preview()
    draft.confirm()
    return draft


async def test_finalize_sends_with_recipients_and_attachments() -> None:
    service = FakeEmailService()
    draft = _confirmed_draft()
    message_id = await finalize_and_send(draft, service, _settings())
    assert message_id == "msg-123"
    assert draft.state is DraftState.SENT
    call = service.calls[0]
    assert call["to"] == "kalex7878@gmail.com"
    assert call["cc"] == "sagy.galor@fursa.org.il,sagy.galor@portlandtrust.org.il"
    assert "Homework Submission" in call["subject"]
    assert len(call["attachments"]) == 1


async def test_double_send_guarded() -> None:
    service = FakeEmailService()
    draft = _confirmed_draft()
    await finalize_and_send(draft, service, _settings())
    with pytest.raises(ValueError, match="already sent"):
        await finalize_and_send(draft, service, _settings())


async def test_send_failure_keeps_draft_confirmed() -> None:
    service = FakeEmailService(fail=True)
    draft = _confirmed_draft()
    with pytest.raises(RuntimeError):
        await finalize_and_send(draft, service, _settings())
    assert draft.state is DraftState.CONFIRMED


def test_backend_selects_gmail_when_oauth() -> None:
    settings = Settings(
        google_oauth_refresh_token="r", google_oauth_client_id="c"  # type: ignore[arg-type]
    )
    assert isinstance(build_email_service(settings), GmailEmailService)


def test_backend_selects_smtp_when_only_smtp() -> None:
    settings = Settings(
        smtp_host="smtp.x", smtp_user="u", smtp_pass="p"  # type: ignore[arg-type]
    )
    assert isinstance(build_email_service(settings), SmtpEmailService)


def test_backend_none_when_unconfigured() -> None:
    assert build_email_service(Settings()) is None
