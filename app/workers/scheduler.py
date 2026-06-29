"""APScheduler wiring: Drive watcher, schedule refresh, and nightly precompute.

Runs inside the bot's event loop in single-process mode (default), or standalone in the
worker. Each job is registered only when its component is provided.
"""

from __future__ import annotations

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.core.logging import get_logger
from app.core.settings import Settings
from app.workers.drive_watcher import DriveWatcher
from app.workers.precompute import Precomputer
from app.workers.schedule_refresh import ScheduleRefresher

_log = get_logger("worker.scheduler")


def build_scheduler(
    settings: Settings,
    *,
    drive_watcher: DriveWatcher | None = None,
    schedule_refresher: ScheduleRefresher | None = None,
    precomputer: Precomputer | None = None,
) -> AsyncIOScheduler:
    """Build an AsyncIOScheduler with whichever jobs are available."""
    scheduler = AsyncIOScheduler(timezone="UTC")
    jobs: list[str] = []
    if drive_watcher is not None:
        scheduler.add_job(
            drive_watcher.run_once,
            trigger="interval",
            minutes=settings.drive_poll_minutes,
            id="drive_watcher",
            max_instances=1,
            coalesce=True,
        )
        jobs.append("drive_watcher")
    if schedule_refresher is not None:
        scheduler.add_job(
            schedule_refresher.run_once,
            trigger="interval",
            hours=settings.schedule_refresh_hours,
            id="schedule_refresh",
            max_instances=1,
            coalesce=True,
        )
        jobs.append("schedule_refresh")
    if precomputer is not None:
        scheduler.add_job(
            precomputer.run_once,
            trigger="cron",
            hour=settings.precompute_hour,
            id="precompute",
            max_instances=1,
            coalesce=True,
        )
        jobs.append("precompute")
    _log.info("scheduler_built", jobs=jobs)
    return scheduler
