"""Shared pytest fixtures.

The whole suite mocks external services — no live Telegram, Google, LLM, Gmail, or ASR
calls ever happen. Fixtures here provide settings and mocked Telegram update objects.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from app.core.settings import Settings, get_settings


@pytest.fixture(autouse=True)
def _isolate_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Isolate Settings from the developer's real ``.env`` and env vars.

    Runs each test from a clean temp CWD (so the project ``.env`` isn't picked up) with
    the relevant allowlist/token env vars cleared, and a fresh Settings cache.
    """
    from app.repo.db import reset_engine
    from app.services.llm import get_model_registry
    from app.services.summaries import _SHARED_SUMMARY_CACHE

    get_settings.cache_clear()
    get_model_registry.cache_clear()
    reset_engine()
    _SHARED_SUMMARY_CACHE.clear()
    for var in ("TELEGRAM_BOT_TOKEN", "OWNER_TELEGRAM_IDS", "ADMIN_TELEGRAM_IDS"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.chdir(tmp_path)
    yield
    get_settings.cache_clear()
    get_model_registry.cache_clear()
    reset_engine()


@pytest.fixture
def settings() -> Settings:
    """A Settings instance with a dummy token and admin allowlist for tests."""
    return Settings(
        telegram_bot_token="test-token",  # type: ignore[arg-type]
        admin_telegram_ids=(111, 222),  # type: ignore[arg-type]
    )


@pytest.fixture
async def db_sessionmaker(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[object]:
    """Provide an initialized, isolated SQLite datastore for repository tests."""
    from app.repo.db import get_engine, get_sessionmaker, init_db, reset_engine

    db_path = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_path.as_posix()}")
    get_settings.cache_clear()
    reset_engine()
    await init_db()
    yield get_sessionmaker()
    await get_engine().dispose()  # close aiosqlite threads before the loop ends
    reset_engine()


@pytest.fixture
def mock_message() -> MagicMock:
    """A mocked Telegram message with an async ``reply_text``."""
    message = MagicMock()
    message.text = "hello"
    message.reply_text = AsyncMock()
    return message


@pytest.fixture
def mock_update(mock_message: MagicMock) -> MagicMock:
    """A mocked Telegram update wrapping ``mock_message``."""
    update = MagicMock()
    update.effective_message = mock_message
    update.effective_user = MagicMock(id=999)
    return update
