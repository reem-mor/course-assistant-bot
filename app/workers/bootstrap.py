"""Builds the scheduler's job components from settings + a Telegram bot.

Shared by single-process mode (scheduler inside the bot) and the standalone worker. Each
component is built only when its dependencies are configured, so the scheduler degrades
gracefully.
"""

from __future__ import annotations

from typing import Any

from app.core.logging import get_logger
from app.core.settings import Settings
from app.domain.lesson_map import LessonMap
from app.repo.db import get_sessionmaker
from app.repo.repositories import BroadcastLogRepo, DriveStateRepo, SubscriberRepo
from app.services.drive import try_get_drive_service
from app.services.lesson_map_store import YamlLessonMapStore
from app.services.llm import try_get_model_registry
from app.services.notifier import TelegramNotifier
from app.services.schedule import get_schedule_service
from app.workers.drive_watcher import DriveWatcher
from app.workers.precompute import Precomputer
from app.workers.schedule_refresh import ScheduleRefresher

_log = get_logger("worker.bootstrap")


def build_components(
    settings: Settings, bot: Any
) -> tuple[DriveWatcher | None, ScheduleRefresher | None, Precomputer | None]:
    """Build (drive_watcher, schedule_refresher, precomputer) from current config."""
    drive = try_get_drive_service()
    registry = try_get_model_registry()
    lesson_map: LessonMap = YamlLessonMapStore().load()
    sessionmaker = get_sessionmaker()

    watcher: DriveWatcher | None = None
    if drive is not None and bot is not None:
        notifier = TelegramNotifier(
            bot,
            SubscriberRepo(sessionmaker),
            BroadcastLogRepo(sessionmaker),
            rate_per_sec=settings.broadcast_rate_per_sec,
        )
        watcher = DriveWatcher(drive, lesson_map, notifier, DriveStateRepo(sessionmaker))

    refresher: ScheduleRefresher | None = None
    if bot is not None:
        refresher = ScheduleRefresher(get_schedule_service(), bot, settings)

    precomputer: Precomputer | None = None
    if drive is not None and registry is not None:
        precomputer = Precomputer(drive, lesson_map, registry)

    _log.info(
        "components_built",
        watcher=watcher is not None,
        refresher=refresher is not None,
        precomputer=precomputer is not None,
    )
    return watcher, refresher, precomputer
