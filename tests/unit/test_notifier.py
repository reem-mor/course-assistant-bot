"""Tests for TelegramNotifier: fan-out, idempotency, partial failure, RetryAfter."""

from __future__ import annotations

from typing import Any

from app.repo.repositories import BroadcastLogRepo, SubscriberRepo
from app.services.notifier import TelegramNotifier
from telegram.error import RetryAfter


class FakeBot:
    def __init__(self, *, fail_ids: set[int] | None = None) -> None:
        self.sent: list[int] = []
        self.fail_ids = fail_ids or set()

    async def send_message(self, *, chat_id: int, text: str) -> None:
        if chat_id in self.fail_ids:
            raise RuntimeError("blocked")
        self.sent.append(chat_id)


class RetryOnceBot:
    def __init__(self) -> None:
        self.sent: list[int] = []
        self._raised = False

    async def send_message(self, *, chat_id: int, text: str) -> None:
        if not self._raised:
            self._raised = True
            raise RetryAfter(0.01)
        self.sent.append(chat_id)


async def _notifier(bot: Any, db_sessionmaker: Any) -> TelegramNotifier:
    subs = SubscriberRepo(db_sessionmaker)
    await subs.upsert(1, language="en")
    await subs.upsert(2, language="en")
    return TelegramNotifier(bot, subs, BroadcastLogRepo(db_sessionmaker), rate_per_sec=1000)


async def test_broadcast_reaches_all(db_sessionmaker: Any) -> None:
    bot = FakeBot()
    notifier = await _notifier(bot, db_sessionmaker)
    result = await notifier.broadcast(idempotency_key="k1", message="hi")
    assert result.sent == 2
    assert result.failed == 0
    assert set(bot.sent) == {1, 2}


async def test_broadcast_idempotent(db_sessionmaker: Any) -> None:
    bot = FakeBot()
    notifier = await _notifier(bot, db_sessionmaker)
    await notifier.broadcast(idempotency_key="dup", message="hi")
    bot.sent.clear()
    second = await notifier.broadcast(idempotency_key="dup", message="hi")
    assert second.sent == 0 and second.failed == 0
    assert bot.sent == []  # not re-sent


async def test_partial_failure_counted(db_sessionmaker: Any) -> None:
    bot = FakeBot(fail_ids={2})
    notifier = await _notifier(bot, db_sessionmaker)
    result = await notifier.broadcast(idempotency_key="k2", message="hi")
    assert result.sent == 1
    assert result.failed == 1


async def test_retry_after_then_success(db_sessionmaker: Any) -> None:
    bot = RetryOnceBot()
    subs = SubscriberRepo(db_sessionmaker)
    await subs.upsert(1, language="en")
    notifier = TelegramNotifier(
        bot, subs, BroadcastLogRepo(db_sessionmaker), rate_per_sec=1000
    )
    result = await notifier.broadcast(idempotency_key="k3", message="hi")
    assert result.sent == 1
    assert bot.sent == [1]
