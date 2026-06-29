"""Integration test for the submission conversation step handlers (mocked Telegram)."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from app.bot import submission_flow
from app.bot.submission_flow import (
    ATTACH,
    CHALLENGES,
    DATE,
    NAME,
    PREVIEW,
    TECH,
    TOPIC,
    WORK,
    on_button,
    receive_challenges,
    receive_date,
    receive_name,
    receive_tech,
    receive_topic,
    receive_work,
    show_preview,
    start_submission,
)
from telegram.ext import ConversationHandler


class FakeEmailService:
    def __init__(self) -> None:
        self.calls = 0

    async def send(self, **kwargs: Any) -> str:
        self.calls += 1
        return "msg-xyz"


def _ctx() -> MagicMock:
    ctx = MagicMock()
    ctx.user_data = {}
    return ctx


def _text_update(text: str) -> MagicMock:
    update = MagicMock()
    msg = MagicMock()
    msg.text = text
    msg.document = None
    msg.reply_text = AsyncMock()
    update.effective_message = msg
    update.effective_user = MagicMock(id=1)
    return update


async def test_full_flow_to_preview_and_send(monkeypatch: pytest.MonkeyPatch) -> None:
    service = FakeEmailService()
    monkeypatch.setattr(submission_flow, "_email_service", lambda: service)
    ctx = _ctx()

    assert await start_submission(_text_update("/submit"), ctx) == NAME
    assert await receive_name(_text_update("John Doe"), ctx) == TOPIC
    assert await receive_topic(_text_update("Python Basics"), ctx) == DATE
    assert await receive_date(_text_update("12/05/2026"), ctx) == WORK
    assert await receive_work(_text_update("Built a CLI app"), ctx) == TECH
    assert await receive_tech(_text_update("Python, argparse"), ctx) == CHALLENGES
    assert await receive_challenges(_text_update("-"), ctx) == ATTACH

    preview_update = _text_update("/done")
    assert await show_preview(preview_update, ctx) == PREVIEW
    preview_text = preview_update.effective_message.reply_text.await_args.args[0]
    assert "Submission preview:" in preview_text
    assert "[Oz VeRuach] Homework Submission" in preview_text

    # Send with no attachment/link warns first.
    btn = MagicMock()
    btn.callback_query = MagicMock()
    btn.callback_query.data = "sub:send"
    btn.callback_query.answer = AsyncMock()
    btn.effective_message = MagicMock(reply_text=AsyncMock())
    btn.effective_user = MagicMock(id=1)
    assert await on_button(btn, ctx) == PREVIEW
    assert service.calls == 0  # warned, not sent

    # Second press confirms and sends.
    assert await on_button(btn, ctx) == ConversationHandler.END
    assert service.calls == 1


async def test_name_remembered_skips_to_topic() -> None:
    ctx = _ctx()
    ctx.user_data["full_name"] = "Jane Doe"
    assert await start_submission(_text_update("/submit"), ctx) == TOPIC


async def test_cancel_button_ends() -> None:
    ctx = _ctx()
    await start_submission(_text_update("/submit"), ctx)
    btn = MagicMock()
    btn.callback_query = MagicMock()
    btn.callback_query.data = "sub:cancel"
    btn.callback_query.answer = AsyncMock()
    btn.effective_message = MagicMock(reply_text=AsyncMock())
    assert await on_button(btn, ctx) == ConversationHandler.END
