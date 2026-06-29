"""Tests for the cooldown rate limiter and metrics counters."""

from __future__ import annotations

import time

from app.core.metrics import Metrics
from app.core.ratelimit import CooldownLimiter


def test_cooldown_blocks_then_allows() -> None:
    limiter = CooldownLimiter(cooldown_sec=0.2)
    assert limiter.allow(1, "summarize") is True
    assert limiter.allow(1, "summarize") is False  # within cooldown
    assert limiter.allow(2, "summarize") is True  # different user
    time.sleep(0.25)
    assert limiter.allow(1, "summarize") is True  # cooldown elapsed


def test_retry_after_decreases() -> None:
    limiter = CooldownLimiter(cooldown_sec=10)
    limiter.allow(1, "op")
    assert 0 < limiter.retry_after(1, "op") <= 10
    assert limiter.retry_after(99, "op") == 0.0


def test_metrics_increment_and_render() -> None:
    metrics = Metrics()
    metrics.inc("intent_schedule_total")
    metrics.inc("intent_schedule_total", 2)
    metrics.inc("errors_total")
    snap = metrics.snapshot()
    assert snap["intent_schedule_total"] == 3
    text = metrics.render_prometheus()
    assert "oz_intent_schedule_total 3" in text
    assert "# TYPE oz_errors_total counter" in text
