"""Tests for Phase 7 admin commands: /admin, /help, /announce, /schedule_update."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from app.bot import admin_handlers, announce_flow
from app.core.settings import Settings
from app.repo.repositories import AdminRepo
from app.services.notifier import BroadcastResult
from app.services.schedule_store import ScheduleStore

_SCHEDULE = """
course:
  name: "Test"
  start: "2026-04-26"
  end: "2026-07-30"
  timezone: "Asia/Jerusalem"
sessions:
  - {week: 1, date: "2026-04-29", day: Wed, time: "09:00-15:15", title: "Old",
     instructor: "Alex", type: technical}
"""


def _update(text: str, user_id: int) -> MagicMock:
    update = MagicMock()
    msg = MagicMock()
    msg.text = text
    msg.reply_text = AsyncMock()
    update.effective_message = msg
    update.effective_user = MagicMock(id=user_id)
    return update


def _ctx(*args: str) -> MagicMock:
    ctx = MagicMock()
    ctx.args = list(args)
    ctx.user_data = {}
    ctx.bot = MagicMock()
    return ctx


def _as_owner(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        admin_handlers, "get_settings", lambda: Settings(owner_telegram_ids=(7,))  # type: ignore[arg-type]
    )


async def test_admin_add_and_list(
    db_sessionmaker: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    _as_owner(monkeypatch)
    monkeypatch.setattr(admin_handlers, "_admin_repo", lambda: AdminRepo(db_sessionmaker))
    await admin_handlers.admin_command(_update("/admin", 7), _ctx("add", "555"))
    assert 555 in await AdminRepo(db_sessionmaker).list_ids()


async def test_admin_requires_owner(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(admin_handlers, "get_settings", lambda: Settings())
    update = _update("/admin", 42)
    await admin_handlers.admin_command(update, _ctx("add", "555"))
    assert "owner only" in update.effective_message.reply_text.await_args.args[0]


async def test_help_shows_owner_section(monkeypatch: pytest.MonkeyPatch) -> None:
    _as_owner(monkeypatch)
    update = _update("/help", 7)
    await admin_handlers.help_command(update, _ctx())
    sent = update.effective_message.reply_text.await_args.args[0]
    assert "Owner:" in sent
    assert "/announce" in sent


async def test_schedule_update_writes_override(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _as_owner(monkeypatch)
    path = tmp_path / "schedule.yaml"
    path.write_text(_SCHEDULE, encoding="utf-8")
    monkeypatch.setattr(announce_flow, "_store", lambda: ScheduleStore(path))
    update = _update("/schedule_update", 7)
    await announce_flow.schedule_update_command(
        update, _ctx("2026-04-29", "title=New Title", "time=10:00-12:00")
    )
    sent = update.effective_message.reply_text.await_args.args[0]
    assert "updated" in sent
    assert "New Title" in path.read_text(encoding="utf-8")
    assert "manual: true" in path.read_text(encoding="utf-8")


async def test_announce_preview_then_send(monkeypatch: pytest.MonkeyPatch) -> None:
    _as_owner(monkeypatch)

    class FakeNotifier:
        async def broadcast(self, *, idempotency_key: str, message: str) -> BroadcastResult:
            return BroadcastResult(sent=3, failed=0)

    monkeypatch.setattr(announce_flow, "_notifier", lambda bot: FakeNotifier())
    ctx = _ctx("Exam", "moved", "to", "Tuesday")
    update = _update("/announce", 7)
    await announce_flow.announce_command(update, ctx)
    assert "pending_announcement" in ctx.user_data

    btn = _update("send", 7)  # English text -> English reply
    btn.callback_query = MagicMock()
    btn.callback_query.data = "ann:send"
    btn.callback_query.answer = AsyncMock()
    await announce_flow.announce_callback(btn, ctx)
    sent = btn.effective_message.reply_text.await_args.args[0]
    assert "3 delivered" in sent
