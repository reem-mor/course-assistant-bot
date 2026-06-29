"""Test that the scheduler registers the expected jobs."""

from __future__ import annotations

from typing import Any, cast

from app.core.settings import Settings
from app.workers.drive_watcher import DriveWatcher
from app.workers.precompute import Precomputer
from app.workers.schedule_refresh import ScheduleRefresher
from app.workers.scheduler import build_scheduler


class _Stub:
    async def run_once(self) -> int:
        return 0


def test_all_jobs_registered() -> None:
    stub = _Stub()
    scheduler = build_scheduler(
        Settings(),
        drive_watcher=cast(DriveWatcher, stub),
        schedule_refresher=cast(ScheduleRefresher, stub),
        precomputer=cast(Precomputer, stub),
    )
    ids = {job.id for job in scheduler.get_jobs()}
    assert ids == {"drive_watcher", "schedule_refresh", "precompute"}


def test_partial_registration() -> None:
    stub: Any = _Stub()
    scheduler = build_scheduler(Settings(), drive_watcher=stub)
    ids = {job.id for job in scheduler.get_jobs()}
    assert ids == {"drive_watcher"}
