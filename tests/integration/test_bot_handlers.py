"""Integration tests for Phase 0 bot handlers with mocked Telegram objects.

No live Telegram calls: ``reply_text`` is an AsyncMock we assert against.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from app.bot.handlers import myid_command, start_command, text_message
from app.core.settings import Settings


async def test_start_replies_in_hebrew_for_hebrew_text(mock_update: MagicMock) -> None:
    mock_update.effective_message.text = "שלום"
    await start_command(mock_update, MagicMock())
    mock_update.effective_message.reply_text.assert_awaited_once()
    sent = mock_update.effective_message.reply_text.await_args.args[0]
    assert "עוז ורוח" in sent


async def test_start_replies_in_english_for_english_text(mock_update: MagicMock) -> None:
    mock_update.effective_message.text = "hello there"
    await start_command(mock_update, MagicMock())
    sent = mock_update.effective_message.reply_text.await_args.args[0]
    assert "Oz VeRuach" in sent


async def test_echo_returns_text_for_unrecognized(mock_update: MagicMock) -> None:
    mock_update.effective_message.text = "ping"
    await text_message(mock_update, MagicMock())
    sent = mock_update.effective_message.reply_text.await_args.args[0]
    assert sent == "You said: ping"


async def test_echo_empty_message_prompts(mock_update: MagicMock) -> None:
    # Whitespace-only -> ambiguous language -> Hebrew default per spec.
    mock_update.effective_message.text = "   "
    await text_message(mock_update, MagicMock())
    sent = mock_update.effective_message.reply_text.await_args.args[0]
    assert sent == "לא קיבלתי טקסט לטיפול."


async def test_echo_handles_reply_failure_with_fallback() -> None:
    message = MagicMock()
    message.text = "boom"
    # First reply (the echo) raises; handler must catch and send a fallback.
    message.reply_text = AsyncMock(side_effect=[RuntimeError("network"), None])
    update = MagicMock()
    update.effective_message = message
    update.effective_user = MagicMock(id=1)

    await text_message(update, MagicMock())

    assert message.reply_text.await_count == 2
    fallback = message.reply_text.await_args.args[0]
    assert "try again" in fallback


async def test_myid_reports_id_and_owner_role(
    mock_update: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    mock_update.effective_user = MagicMock(id=999)
    mock_update.effective_message.text = "/myid"
    monkeypatch.setattr(
        "app.bot.handlers.get_settings",
        lambda: Settings(owner_telegram_ids=(999,)),  # type: ignore[arg-type]
    )
    await myid_command(mock_update, MagicMock())
    sent = mock_update.effective_message.reply_text.await_args.args[0]
    assert "999" in sent
    assert "owner" in sent


async def test_myid_reports_student_for_unknown_user(
    mock_update: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    mock_update.effective_user = MagicMock(id=42)
    mock_update.effective_message.text = "hello"
    monkeypatch.setattr(
        "app.bot.handlers.get_settings",
        lambda: Settings(),
    )
    await myid_command(mock_update, MagicMock())
    sent = mock_update.effective_message.reply_text.await_args.args[0]
    assert "42" in sent
    assert "student" in sent


async def test_handlers_noop_when_no_message() -> None:
    update = MagicMock()
    update.effective_message = None
    # Should not raise.
    await start_command(update, MagicMock())
    await text_message(update, MagicMock())
