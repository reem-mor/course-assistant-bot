"""Unit tests for the lesson_map model, YAML store, and auto-suggester."""

from __future__ import annotations

from pathlib import Path

from app.services.lesson_map_store import YamlLessonMapStore
from app.services.schedule import YamlScheduleService
from app.services.suggester import suggest_recording_links

_SEED = """
roots:
  course_folder: "ROOT"
  recordings_folder: "REC"
  presentations_folder: "PRES"
  hw_procedure_doc: "HWDOC"
recordings_by_alex_label:
  1: "REC1"
  2: "REC2"
  7: "REC7"
session_links: {}
"""


def _store(tmp_path: Path) -> YamlLessonMapStore:
    path = tmp_path / "lesson_map.yaml"
    path.write_text(_SEED, encoding="utf-8")
    return YamlLessonMapStore(path)


def test_loads_seed(tmp_path: Path) -> None:
    lesson_map = _store(tmp_path).load()
    assert lesson_map.roots.course_folder == "ROOT"
    assert lesson_map.recordings_by_alex_label[2] == "REC2"
    assert lesson_map.session_links == {}


def test_recording_folder_by_label(tmp_path: Path) -> None:
    lesson_map = _store(tmp_path).load()
    assert lesson_map.recording_folder_by_label(7) == "REC7"
    assert lesson_map.recording_folder_by_label(99) is None


def test_unmapped_session_resolves_to_none(tmp_path: Path) -> None:
    lesson_map = _store(tmp_path).load()
    assert lesson_map.recording_folder_for_session("2026-04-29") is None


def test_set_link_round_trip(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.set_link("2026-04-29", recording_alex_label=1, presentation_alex_label=1)
    reloaded = store.load()
    assert reloaded.recording_folder_for_session("2026-04-29") == "REC1"
    assert reloaded.presentation_label_for_session("2026-04-29") == 1


def test_set_link_persists_to_disk(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.set_link("2026-05-06", recording_alex_label=2, presentation_alex_label=None)
    # A fresh store reading the same file sees the change.
    fresh = YamlLessonMapStore(tmp_path / "lesson_map.yaml").load()
    assert "2026-05-06" in fresh.session_links


def test_real_seed_loads() -> None:
    # The committed data/lesson_map.yaml parses and has the known Alex folders.
    lesson_map = YamlLessonMapStore().load()
    assert lesson_map.recording_folder_by_label(2) == "1Fr2dFnA4eOScaOww9n860pe0sOx6YgnT"
    assert lesson_map.recording_folder_by_label(7) is not None  # exists but empty
    assert lesson_map.session_links == {}


def test_suggester_pairs_chronologically(tmp_path: Path) -> None:
    lesson_map = _store(tmp_path).load()
    schedule = YamlScheduleService.from_yaml()
    suggestions = suggest_recording_links(schedule, lesson_map)
    # Labels available: 1, 2, 7 -> three proposals for the first three technical sessions.
    assert len(suggestions) == 3
    assert suggestions[0].recording_alex_label == 1
    # First technical session is 2026-04-29.
    assert suggestions[0].session_date == "2026-04-29"


def test_suggester_skips_already_linked(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.set_link("2026-04-29", recording_alex_label=1, presentation_alex_label=None)
    schedule = YamlScheduleService.from_yaml()
    suggestions = suggest_recording_links(schedule, store.load())
    assert all(s.session_date != "2026-04-29" for s in suggestions)
