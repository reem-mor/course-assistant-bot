"""Integration tests for the owner-gated /map command."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from app.bot import admin_handlers
from app.core.settings import Settings
from app.services.lesson_map_store import YamlLessonMapStore

_SEED = """
roots:
  course_folder: "ROOT"
  recordings_folder: "REC"
  presentations_folder: "PRES"
  hw_procedure_doc: "HWDOC"
recordings_by_alex_label:
  1: "REC1"
session_links: {}
"""


def _ctx(*args: str) -> MagicMock:
    ctx = MagicMock()
    ctx.args = list(args)
    return ctx


async def test_non_owner_refused(mock_update: MagicMock, monkeypatch: pytest.MonkeyPatch) -> None:
    mock_update.effective_user = MagicMock(id=42)
    mock_update.effective_message.text = "/map"
    monkeypatch.setattr(admin_handlers, "get_settings", lambda: Settings())
    await admin_handlers.map_command(mock_update, _ctx())
    sent = mock_update.effective_message.reply_text.await_args.args[0]
    assert "owner only" in sent


async def test_owner_can_view_map(
    mock_update: MagicMock, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    path = tmp_path / "lesson_map.yaml"
    path.write_text(_SEED, encoding="utf-8")
    mock_update.effective_user = MagicMock(id=7)
    mock_update.effective_message.text = "/map"
    monkeypatch.setattr(
        admin_handlers, "get_settings", lambda: Settings(owner_telegram_ids=(7,))  # type: ignore[arg-type]
    )
    monkeypatch.setattr(admin_handlers, "_store", lambda: YamlLessonMapStore(path))
    await admin_handlers.map_command(mock_update, _ctx())
    sent = mock_update.effective_message.reply_text.await_args.args[0]
    assert "Lesson map" in sent
    assert "Lesson 1: REC1" in sent


async def test_owner_link_round_trip(
    mock_update: MagicMock, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    path = tmp_path / "lesson_map.yaml"
    path.write_text(_SEED, encoding="utf-8")
    mock_update.effective_user = MagicMock(id=7)
    mock_update.effective_message.text = "/map link"
    monkeypatch.setattr(
        admin_handlers, "get_settings", lambda: Settings(owner_telegram_ids=(7,))  # type: ignore[arg-type]
    )
    monkeypatch.setattr(admin_handlers, "_store", lambda: YamlLessonMapStore(path))
    await admin_handlers.map_command(
        mock_update, _ctx("link", "2026-04-29", "rec=1", "pres=1")
    )
    sent = mock_update.effective_message.reply_text.await_args.args[0]
    assert "Saved" in sent
    reloaded = YamlLessonMapStore(path).load()
    assert reloaded.recording_folder_for_session("2026-04-29") == "REC1"
