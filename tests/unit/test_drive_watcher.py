"""Tests for the Drive watcher: silent first run, no double-notify, re-notify on change."""

from __future__ import annotations

from typing import Any

from app.domain.lesson_map import LessonMap, LessonRoots
from app.repo.repositories import DriveStateRepo
from app.services.notifier import BroadcastResult
from app.workers.drive_watcher import DriveWatcher

from tests.fixtures.drive_fixtures import FakeDriveService

_FOLDER = "application/vnd.google-apps.folder"
_DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _tree() -> dict[str, list[dict[str, Any]]]:
    return {
        "REC_ROOT": [{"id": "L1", "title": "Lesson 1", "mimeType": _FOLDER}],
        "L1": [{"id": "vid1", "title": "part 1.mp4", "mimeType": "video/mp4",
                "modifiedTime": "m1"}],
        "PRES_ROOT": [{"id": "L2", "title": "Lesson 2", "mimeType": _FOLDER}],
        "L2": [{"id": "doc1", "title": "hw.docx", "mimeType": _DOCX, "modifiedTime": "m1"}],
    }


def _lesson_map() -> LessonMap:
    return LessonMap(
        roots=LessonRoots(
            course_folder="c", recordings_folder="REC_ROOT",
            presentations_folder="PRES_ROOT", hw_procedure_doc="h",
        ),
        recordings_by_alex_label={1: "L1"},
        session_links={},
    )


class RecordingNotifier:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    async def broadcast(self, *, idempotency_key: str, message: str) -> BroadcastResult:
        self.calls.append((idempotency_key, message))
        return BroadcastResult(sent=1, failed=0)


async def test_first_run_seeds_silently(db_sessionmaker: Any) -> None:
    tree = _tree()
    notifier = RecordingNotifier()
    watcher = DriveWatcher(
        FakeDriveService(tree), _lesson_map(), notifier, DriveStateRepo(db_sessionmaker)
    )
    broadcasts = await watcher.run_once()
    assert broadcasts == 0
    assert notifier.calls == []
    # State is now seeded.
    assert not await DriveStateRepo(db_sessionmaker).is_empty()


async def test_no_double_notify(db_sessionmaker: Any) -> None:
    tree = _tree()
    notifier = RecordingNotifier()
    watcher = DriveWatcher(
        FakeDriveService(tree), _lesson_map(), notifier, DriveStateRepo(db_sessionmaker)
    )
    await watcher.run_once()  # seed
    second = await watcher.run_once()  # nothing changed
    assert second == 0
    assert notifier.calls == []


async def test_new_file_broadcasts_once(db_sessionmaker: Any) -> None:
    tree = _tree()
    notifier = RecordingNotifier()
    drive = FakeDriveService(tree)
    watcher = DriveWatcher(drive, _lesson_map(), notifier, DriveStateRepo(db_sessionmaker))
    await watcher.run_once()  # seed

    tree["L2"].append(
        {"id": "doc2", "title": "extra-hw.docx", "mimeType": _DOCX, "modifiedTime": "m1"}
    )
    broadcasts = await watcher.run_once()
    assert broadcasts == 1
    assert len(notifier.calls) == 1
    assert "extra-hw.docx" in notifier.calls[0][1]


async def test_changed_mtime_renotifies(db_sessionmaker: Any) -> None:
    tree = _tree()
    notifier = RecordingNotifier()
    drive = FakeDriveService(tree)
    watcher = DriveWatcher(drive, _lesson_map(), notifier, DriveStateRepo(db_sessionmaker))
    await watcher.run_once()  # seed

    tree["L1"][0]["modifiedTime"] = "m2"  # recording re-uploaded
    broadcasts = await watcher.run_once()
    assert broadcasts == 1
    assert "part 1.mp4" in notifier.calls[0][1]
