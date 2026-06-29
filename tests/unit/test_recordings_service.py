"""Unit tests for RecordingsService (6.6) covering C2/C3/C4 quirks."""

from __future__ import annotations

from datetime import datetime

from app.services.lesson_map_store import YamlLessonMapStore
from app.services.recordings import RecordingsService
from app.services.schedule import ISRAEL_TZ, YamlScheduleService

from tests.fixtures.drive_fixtures import FakeDriveService


def _now() -> datetime:
    return datetime(2026, 6, 18, 12, tzinfo=ISRAEL_TZ)


def _service() -> RecordingsService:
    lesson_map = YamlLessonMapStore().load()
    schedule = YamlScheduleService.from_yaml(now_provider=_now)
    return RecordingsService(FakeDriveService(), lesson_map, schedule)


async def test_by_alex_label_returns_links_with_gap() -> None:
    result = await _service().by_alex_label(2)
    assert result.linked
    assert not result.empty
    assert [p.part_index for p in result.parts] == [1, 3]
    assert all(p.view_url.startswith("https://drive.google.com/file/d/") for p in result.parts)


async def test_empty_folder_is_not_uploaded() -> None:
    result = await _service().by_alex_label(7)  # Lesson 7 is empty (C3)
    assert result.linked
    assert result.empty
    assert result.parts == []


async def test_unknown_label_not_linked() -> None:
    result = await _service().by_alex_label(99)
    assert not result.linked


async def test_all_with_recordings_lists_known_folders() -> None:
    results = await _service().all_with_recordings()
    labels = {r.label for r in results}
    assert "Lesson 1" in labels
    assert "Lesson 7" in labels  # present but empty
    # Lesson 2 has parts; Lesson 7 does not.
    by_label = {r.label: r for r in results}
    assert by_label["Lesson 2"].parts
    assert by_label["Lesson 7"].parts == []


async def test_last_returns_none_without_session_links() -> None:
    # The conservative seed has no session_links, so "last" cannot resolve a recording.
    assert await _service().last() is None
