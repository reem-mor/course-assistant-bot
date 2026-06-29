"""Integration test: summarize text routing -> formatted reply (mocked Drive + model)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from app.bot import summary_handlers
from app.bot.handlers import text_message
from app.services import summaries
from app.services.summaries import SummaryService

from tests.fixtures.drive_fixtures import FakeDriveService


class _FakeChatModel:
    async def complete(self, *, system: str, prompt: str, max_tokens: int) -> str:
        return "OVERVIEW\n- point"


class _FakeRegistry:
    def for_role(self, role: object) -> _FakeChatModel:
        return _FakeChatModel()


@pytest.fixture(autouse=True)
def _patch(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_extract(drive: object, file: dict[str, object]) -> str:
        return f"text of {file.get('name')}"

    monkeypatch.setattr(summaries, "extract_text", fake_extract)

    def fake_service() -> SummaryService:
        from app.services.lesson_map_store import YamlLessonMapStore

        return SummaryService(FakeDriveService(), YamlLessonMapStore().load(), _FakeRegistry())

    monkeypatch.setattr(summary_handlers, "_summary_service", fake_service)


async def test_summarize_lesson_reply(mock_update: MagicMock) -> None:
    mock_update.effective_message.text = "summarize lesson 12"
    await text_message(mock_update, MagicMock())
    sent = mock_update.effective_message.reply_text.await_args.args[0]
    assert "Summary — Lesson 12" in sent
    assert "OVERVIEW" in sent


async def test_summarize_no_materials(
    mock_update: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    def empty_service() -> SummaryService:
        from app.services.lesson_map_store import YamlLessonMapStore

        return SummaryService(FakeDriveService({}), YamlLessonMapStore().load(), _FakeRegistry())

    monkeypatch.setattr(summary_handlers, "_summary_service", empty_service)
    mock_update.effective_message.text = "summarize lesson 99"
    await text_message(mock_update, MagicMock())
    sent = mock_update.effective_message.reply_text.await_args.args[0]
    assert "No materials" in sent
