"""Lightweight health-check HTTP server.

Both the ``bot`` and ``worker`` processes start one of these so an orchestrator
(Docker healthcheck, load balancer, EC2 cron) can probe liveness. Kept dependency-light
on top of ``aiohttp``; it exposes ``/healthz`` and ``/readyz``.
"""

from __future__ import annotations

import time
from typing import Final

from aiohttp import web

from app import __version__
from app.core.logging import get_logger

_log = get_logger("health")

_START_TIME: Final[float] = time.monotonic()


def build_health_app(*, component: str) -> web.Application:
    """Build an aiohttp app exposing health endpoints for a named component."""
    app = web.Application()

    async def healthz(_request: web.Request) -> web.Response:
        return web.json_response(
            {
                "status": "ok",
                "component": component,
                "version": __version__,
                "uptime_seconds": round(time.monotonic() - _START_TIME, 3),
            }
        )

    async def readyz(_request: web.Request) -> web.Response:
        # Phase 0 has no downstream dependencies to gate readiness on.
        return web.json_response({"status": "ready", "component": component})

    async def metrics(_request: web.Request) -> web.Response:
        from app.core.metrics import METRICS

        return web.Response(text=METRICS.render_prometheus(), content_type="text/plain")

    app.router.add_get("/healthz", healthz)
    app.router.add_get("/readyz", readyz)
    app.router.add_get("/metrics", metrics)
    return app


class HealthServer:
    """Manages the lifecycle of the health-check HTTP server."""

    def __init__(self, *, component: str, host: str, port: int) -> None:
        self._component = component
        self._host = host
        self._port = port
        self._runner: web.AppRunner | None = None

    async def start(self) -> None:
        """Start serving health endpoints in the background."""
        app = build_health_app(component=self._component)
        self._runner = web.AppRunner(app)
        await self._runner.setup()
        site = web.TCPSite(self._runner, host=self._host, port=self._port)
        await site.start()
        _log.info(
            "health_server_started",
            component=self._component,
            host=self._host,
            port=self._port,
        )

    async def stop(self) -> None:
        """Gracefully stop the health-check server."""
        if self._runner is not None:
            await self._runner.cleanup()
            self._runner = None
            _log.info("health_server_stopped", component=self._component)
