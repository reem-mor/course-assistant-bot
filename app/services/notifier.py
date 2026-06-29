"""Broadcast notifier with throttling and idempotency.

Sends to subscribers through a token-bucket limiter (Telegram allows ~30 msg/s globally),
backs off on ``RetryAfter``/429, retries a failed chat once, and records a broadcast key in
``broadcast_log`` so the same event is never broadcast twice. The Telegram bot is mocked in
tests.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from app.core.logging import get_logger
from app.repo.repositories import BroadcastLogRepo, SubscriberRepo

_log = get_logger("notifier")


@dataclass(frozen=True, slots=True)
class BroadcastResult:
    """Outcome of a broadcast: how many chats succeeded vs failed."""

    sent: int
    failed: int


@runtime_checkable
class Notifier(Protocol):
    """Sends throttled, idempotent broadcasts to subscribers."""

    async def broadcast(self, *, idempotency_key: str, message: str) -> BroadcastResult: ...


class TokenBucket:
    """A simple async token-bucket rate limiter."""

    def __init__(self, rate_per_sec: float, *, capacity: float | None = None) -> None:
        self._rate = max(rate_per_sec, 0.1)
        self._capacity = capacity if capacity is not None else self._rate
        self._tokens = self._capacity
        self._updated = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Wait until a token is available, then consume one."""
        async with self._lock:
            while True:
                now = time.monotonic()
                self._tokens = min(
                    self._capacity, self._tokens + (now - self._updated) * self._rate
                )
                self._updated = now
                if self._tokens >= 1:
                    self._tokens -= 1
                    return
                await asyncio.sleep((1 - self._tokens) / self._rate)


class TelegramNotifier:
    """Broadcasts messages to subscribers via the Telegram bot."""

    def __init__(
        self,
        bot: Any,
        subscriber_repo: SubscriberRepo,
        broadcast_log_repo: BroadcastLogRepo,
        *,
        rate_per_sec: float = 25.0,
    ) -> None:
        self._bot = bot
        self._subscribers = subscriber_repo
        self._log_repo = broadcast_log_repo
        self._bucket = TokenBucket(rate_per_sec)

    async def _send_one(self, chat_id: int, message: str) -> bool:
        """Send to one chat, honoring a single RetryAfter backoff. Returns success."""
        from telegram.error import RetryAfter

        await self._bucket.acquire()
        try:
            await self._bot.send_message(chat_id=chat_id, text=message)
            return True
        except RetryAfter as exc:
            await asyncio.sleep(float(getattr(exc, "retry_after", 1)))
            try:
                await self._bot.send_message(chat_id=chat_id, text=message)
                return True
            except Exception:
                return False
        except Exception:
            return False

    async def broadcast(self, *, idempotency_key: str, message: str) -> BroadcastResult:
        """Broadcast a message to all active subscribers exactly once per key."""
        if await self._log_repo.seen(idempotency_key):
            _log.info("broadcast_skipped_duplicate", key=idempotency_key)
            return BroadcastResult(sent=0, failed=0)

        chat_ids = await self._subscribers.active_ids()
        failed: list[int] = []
        sent = 0
        for chat_id in chat_ids:
            if await self._send_one(chat_id, message):
                sent += 1
            else:
                failed.append(chat_id)

        # Retry the failures once.
        still_failed = 0
        for chat_id in failed:
            if await self._send_one(chat_id, message):
                sent += 1
            else:
                still_failed += 1

        await self._log_repo.record(idempotency_key, sent=sent, failed=still_failed)
        _log.info("broadcast_done", key=idempotency_key, sent=sent, failed=still_failed)
        return BroadcastResult(sent=sent, failed=still_failed)
