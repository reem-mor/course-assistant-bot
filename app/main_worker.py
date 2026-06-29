"""Entry point for the standalone ``worker`` process (optional split mode).

Single-process mode (default) runs these jobs inside the bot. This entry point exists for
the optional bot/worker split: it hosts the health server and the full scheduler (Drive
watcher + schedule refresh + nightly precompute). Degrades to health-only if the bot token
isn't configured.
"""

from __future__ import annotations

import asyncio
import contextlib
import signal
from typing import Any

from app.core.health import HealthServer
from app.core.logging import configure_logging, get_logger
from app.core.settings import Settings, get_settings
from app.repo.db import init_db
from app.workers.bootstrap import build_components
from app.workers.scheduler import build_scheduler

_log = get_logger("main_worker")


async def _build_bot(settings: Settings) -> Any | None:
    """Build and initialize a standalone Telegram bot, or None if no token."""
    if settings.telegram_bot_token is None:
        _log.warning("worker_degraded", reason="no_bot_token")
        return None
    from telegram import Bot

    bot = Bot(token=settings.require_telegram_token())
    await bot.initialize()
    return bot


async def _run(settings: Settings) -> None:
    health = HealthServer(
        component="worker", host=settings.health_host, port=settings.health_port + 1
    )
    await health.start()
    await init_db()

    bot = await _build_bot(settings)
    scheduler = None
    if bot is not None:
        watcher, refresher, precomputer = build_components(settings, bot)
        scheduler = build_scheduler(
            settings,
            drive_watcher=watcher,
            schedule_refresher=refresher,
            precomputer=precomputer,
        )
        scheduler.start()
        _log.info("worker_started", scheduler="enabled")
    else:
        _log.info("worker_started", scheduler="disabled")

    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        with contextlib.suppress(NotImplementedError):
            loop.add_signal_handler(sig, stop_event.set)

    try:
        await stop_event.wait()
    finally:
        if scheduler is not None:
            scheduler.shutdown(wait=False)
        if bot is not None:
            await bot.shutdown()
        await health.stop()
        _log.info("worker_stopped")


def main() -> None:
    """Configure logging and run the worker process until interrupted."""
    settings = get_settings()
    configure_logging(level=settings.log_level, json_logs=settings.log_json)
    asyncio.run(_run(settings))


if __name__ == "__main__":
    main()
