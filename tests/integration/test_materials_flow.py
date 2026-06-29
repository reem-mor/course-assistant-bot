"""Integration test: materials text routing -> recommendations reply (mocked service)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from app.bot import recommendation_handlers
from app.bot.handlers import text_message
from app.services.recommendations import Recommendations
from app.services.resources_catalog import get_resources_catalog


class FakeService:
    async def recommend(self, *, topic: str, allow_web: bool, language: str) -> Recommendations:
        return Recommendations(curated=get_resources_catalog().lookup("docker"))


@pytest.fixture(autouse=True)
def _patch_service(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(recommendation_handlers, "_service", lambda: FakeService())


async def test_materials_reply(mock_update: MagicMock) -> None:
    mock_update.effective_message.text = "recommended materials for docker"
    await text_message(mock_update, MagicMock())
    sent = mock_update.effective_message.reply_text.await_args.args[0]
    assert "Recommended reading:" in sent
    assert "docker.com" in sent
