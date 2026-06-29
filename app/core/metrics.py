"""In-process metrics counters.

A tiny, dependency-free counter registry exposed as Prometheus-style plain text on the
health server's ``/metrics`` endpoint. Enough for at-a-glance observability without
pulling a full metrics client; a real exporter can be added later.
"""

from __future__ import annotations

import threading


class Metrics:
    """Thread-safe labelless counters."""

    def __init__(self) -> None:
        self._counters: dict[str, float] = {}
        self._lock = threading.Lock()

    def inc(self, name: str, value: float = 1.0) -> None:
        with self._lock:
            self._counters[name] = self._counters.get(name, 0.0) + value

    def snapshot(self) -> dict[str, float]:
        with self._lock:
            return dict(self._counters)

    def render_prometheus(self) -> str:
        """Render counters in Prometheus text exposition format."""
        lines: list[str] = []
        for name, value in sorted(self.snapshot().items()):
            metric = f"oz_{name}"
            lines.append(f"# TYPE {metric} counter")
            lines.append(f"{metric} {value}")
        return "\n".join(lines) + "\n"


# Process-wide singleton.
METRICS = Metrics()
