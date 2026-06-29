"""Integration tests: schedule text routing -> formatted reply (frozen clock, mocked TG)."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

import pytest
from app.bot.handlers import text_message
from app.bot.schedule_handlers import schedule_command
from app.services.schedule import ISRAEL_TZ, YamlScheduleService


def _frozen_now() -> datetime:
    return datetime(2026, 6, 16, 12, tzinfo=ISRAEL_TZ)


def _frozen_service() -> YamlScheduleService:
    return YamlScheduleService.from_yaml(now_provider=_frozen_now)


@pytest.fixture(autouse=True)
def _patch_service(monkeypatch: pytest.MonkeyPatch) -> None:
    """Point the schedule handlers at a frozen-clock service."""
    svc = _frozen_service()
    monkeypatch.setattr("app.bot.schedule_handlers.get_schedule_service", lambda: svc)


async def test_next_lesson_english(mock_update: MagicMock) -> None:
    mock_update.effective_message.text = "next lesson"
    await text_message(mock_update, MagicMock())
    sent = mock_update.effective_message.reply_text.await_args.args[0]
    assert "Next lesson:" in sent
    assert "N8N deep dive" in sent
    assert "17/06/2026" in sent


async def test_next_lesson_hebrew(mock_update: MagicMock) -> None:
    mock_update.effective_message.text = "מתי השיעור הבא?"
    await text_message(mock_update, MagicMock())
    sent = mock_update.effective_message.reply_text.await_args.args[0]
    assert "השיעור הבא:" in sent
    assert "N8N deep dive" in sent


async def test_this_week_lists_sessions(mock_update: MagicMock) -> None:
    mock_update.effective_message.text = "what's on this week"
    await text_message(mock_update, MagicMock())
    sent = mock_update.effective_message.reply_text.await_args.args[0]
    assert "This week" in sent
    # Window 2026-06-14..2026-06-20 contains the N8N deep dive (06-17).
    assert "N8N deep dive" in sent


async def test_schedule_command_full(mock_update: MagicMock) -> None:
    mock_update.effective_message.text = "/schedule"
    await schedule_command(mock_update, MagicMock())
    sent = mock_update.effective_message.reply_text.await_args.args[0]
    assert "Full course schedule:" in sent
    assert "Week 1" in sent
    assert "Week 14" in sent


async def test_non_technical_note_for_workshop(mock_update: MagicMock) -> None:
    # 2026-06-14 (workshop) is in this week's window for the frozen clock.
    mock_update.effective_message.text = "this week"
    await text_message(mock_update, MagicMock())
    sent = mock_update.effective_message.reply_text.await_args.args[0]
    assert "non-technical session" in sent
