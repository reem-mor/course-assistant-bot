"""Integration tests: recording/homework text routing -> formatted replies (mocked Drive)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from app.bot import drive_handlers
from app.bot.handlers import text_message

from tests.fixtures.drive_fixtures import FakeDriveService


@pytest.fixture(autouse=True)
def _fake_drive(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(drive_handlers, "try_get_drive_service", lambda: FakeDriveService())


async def test_specific_recording_returns_links(mock_update: MagicMock) -> None:
    mock_update.effective_message.text = "recording of lesson 2"
    await text_message(mock_update, MagicMock())
    sent = mock_update.effective_message.reply_text.await_args.args[0]
    assert "Recording — Lesson 2" in sent
    assert "drive.google.com/file/d/" in sent
    assert "Part 1" in sent and "Part 3" in sent
    assert "some parts may be missing" in sent  # gap note (C2)


async def test_all_recordings_overview(mock_update: MagicMock) -> None:
    mock_update.effective_message.text = "all recordings"
    await text_message(mock_update, MagicMock())
    sent = mock_update.effective_message.reply_text.await_args.args[0]
    assert "Available recordings:" in sent
    assert "Lesson 7: not uploaded yet" in sent  # C3


async def test_last_recording_unlinked(mock_update: MagicMock) -> None:
    mock_update.effective_message.text = "last recording"
    await text_message(mock_update, MagicMock())
    sent = mock_update.effective_message.reply_text.await_args.args[0]
    assert "No linked recent recording" in sent


async def test_latest_homework_lists_docs(mock_update: MagicMock) -> None:
    mock_update.effective_message.text = "latest homework"
    await text_message(mock_update, MagicMock())
    sent = mock_update.effective_message.reply_text.await_args.args[0]
    assert "Latest homework (Lesson 12)" in sent
    assert "n8n" in sent.lower()


async def test_drive_not_configured(
    mock_update: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(drive_handlers, "try_get_drive_service", lambda: None)
    mock_update.effective_message.text = "all recordings"
    await text_message(mock_update, MagicMock())
    sent = mock_update.effective_message.reply_text.await_args.args[0]
    assert "isn't configured" in sent
