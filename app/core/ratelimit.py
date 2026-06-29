"""Per-user rate limiting for heavy operations.

A simple in-memory cooldown keyed by ``(user_id, op)``: deep summaries, transcription
triggers, and web-augmented recommendations shouldn't be spammable. Process-local is fine
for a single always-on instance; swap for Redis if the bot is ever sharded.
"""

from __future__ import annotations

import time


class CooldownLimiter:
    """Allows an operation per user at most once per ``cooldown`` seconds."""

    def __init__(self, cooldown_sec: float) -> None:
        self._cooldown = cooldown_sec
        self._last: dict[tuple[int, str], float] = {}

    def allow(self, user_id: int, op: str) -> bool:
        """Return True if the op is allowed now, recording the attempt; else False."""
        key = (user_id, op)
        now = time.monotonic()
        last = self._last.get(key)
        if last is not None and (now - last) < self._cooldown:
            return False
        self._last[key] = now
        return True

    def retry_after(self, user_id: int, op: str) -> float:
        """Seconds remaining before the op is allowed again (0 if allowed)."""
        last = self._last.get((user_id, op))
        if last is None:
            return 0.0
        remaining = self._cooldown - (time.monotonic() - last)
        return max(0.0, remaining)
