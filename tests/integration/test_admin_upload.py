"""Tests for the admin upload -> broadcast path and caption parsing."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from app.bot import admin_handlers, admin_upload
from app.bot.admin_upload import handle_admin_upload, parse_caption
from app.core.settings import Settings
from app.services.notifier import BroadcastResult


def test_parse_caption() -> None:
    parsed = parse_caption("lesson 12 homework")
    assert parsed.lesson == 12
    assert parsed.kind == "homework"
    bare = parse_caption(None)
    assert bare.lesson is None and bare.kind == "other"


def _doc_update(caption: str, user_id: int) -> MagicMock:
    update = MagicMock()
    msg = MagicMock()
    msg.caption = caption
    msg.document = MagicMock(file_name="hw.docx", mime_type="application/octet-stream",
                            file_id="fid")
    msg.reply_text = AsyncMock()
    update.effective_message = msg
    update.effective_user = MagicMock(id=user_id)
    return update


class FakeNotifier:
    async def broadcast(self, *, idempotency_key: str, message: str) -> BroadcastResult:
        return BroadcastResult(sent=2, failed=0)


async def test_non_admin_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(admin_handlers, "get_settings", lambda: Settings())
    update = _doc_update("lesson 1 homework", user_id=42)
    await handle_admin_upload(update, MagicMock())
    sent = update.effective_message.reply_text.await_args.args[0]
    assert "admins only" in sent


async def test_admin_broadcast_drive_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        admin_handlers, "get_settings", lambda: Settings(owner_telegram_ids=(7,))  # type: ignore[arg-type]
    )
    monkeypatch.setattr(
        admin_upload, "get_settings", lambda: Settings(owner_telegram_ids=(7,))  # type: ignore[arg-type]
    )
    monkeypatch.setattr(admin_upload, "_notifier", lambda bot: FakeNotifier())

    update = _doc_update("lesson 12 homework", user_id=7)
    await handle_admin_upload(update, MagicMock())

    replies = [c.args[0] for c in update.effective_message.reply_text.await_args_list]
    assert any("Broadcasting" in r for r in replies)
    assert any("2 sent, 0 failed" in r for r in replies)
    assert any("Drive write is disabled" in r for r in replies)
