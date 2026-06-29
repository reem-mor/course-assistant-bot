"""Integration test for the health-check endpoints using aiohttp's test client."""

from __future__ import annotations

from aiohttp.test_utils import TestClient, TestServer
from app.core.health import build_health_app


async def test_healthz_returns_ok() -> None:
    app = build_health_app(component="bot")
    async with TestClient(TestServer(app)) as client:
        resp = await client.get("/healthz")
        assert resp.status == 200
        body = await resp.json()
        assert body["status"] == "ok"
        assert body["component"] == "bot"
        assert "uptime_seconds" in body


async def test_readyz_returns_ready() -> None:
    app = build_health_app(component="worker")
    async with TestClient(TestServer(app)) as client:
        resp = await client.get("/readyz")
        assert resp.status == 200
        body = await resp.json()
        assert body["status"] == "ready"
        assert body["component"] == "worker"
