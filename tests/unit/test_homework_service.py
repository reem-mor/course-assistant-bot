"""Unit tests for HomeworkService (6.4)."""

from __future__ import annotations

from app.services.homework import HomeworkService
from app.services.lesson_map_store import YamlLessonMapStore

from tests.fixtures.drive_fixtures import L2_PRES, FakeDriveService


def _service() -> HomeworkService:
    return HomeworkService(FakeDriveService(), YamlLessonMapStore().load())


async def test_latest_picks_newest_lesson() -> None:
    latest = await _service().latest()
    assert latest is not None
    # Lesson 12's HW has the newest modifiedTime.
    assert "Lesson 12" in latest.lesson_key
    assert len(latest.assignments) == 1
    assert "n8n" in latest.assignments[0].title.lower()


async def test_homework_in_folder_lists_all_docs() -> None:
    # Lesson 2 (flat) has three homework docs.
    hw = await _service().homework_in_folder(L2_PRES)
    names = {m.name for m in hw}
    assert names == {"Jupyter-intro-hw.docx", "Python-intro-hw.docx", "HW2 (2).docx"}


async def test_no_homework_returns_none() -> None:
    service = HomeworkService(FakeDriveService({}), YamlLessonMapStore().load())
    assert await service.latest() is None
