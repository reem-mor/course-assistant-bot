"""Tests for subscription handlers (/start, /stop) with a real in-memory datastore."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from app.bot import subscription_handlers
from app.bot.subscription_handlers import start_command, stop_command
from app.repo.repositories import SubscriberRepo


def _update(text: str, user_id: int) -> MagicMock:
    update = MagicMock()
    msg = MagicMock()
    msg.text = text
    msg.reply_text = AsyncMock()
    update.effective_message = msg
    update.effective_user = MagicMock(id=user_id)
    return update


async def test_start_persists_subscriber(
    db_sessionmaker: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        subscription_handlers, "_subscriber_repo", lambda: SubscriberRepo(db_sessionmaker)
    )
    update = _update("hello", user_id=1)
    await start_command(update, MagicMock())
    assert 1 in await SubscriberRepo(db_sessionmaker).active_ids()
    sent = update.effective_message.reply_text.await_args.args[0]
    assert "Oz VeRuach" in sent


async def test_stop_unsubscribes(
    db_sessionmaker: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = SubscriberRepo(db_sessionmaker)
    monkeypatch.setattr(subscription_handlers, "_subscriber_repo", lambda: repo)
    await repo.upsert(1, language="en")
    update = _update("bye", user_id=1)
    await stop_command(update, MagicMock())
    assert await repo.active_ids() == []
    sent = update.effective_message.reply_text.await_args.args[0]
    assert "unsubscribed" in sent
