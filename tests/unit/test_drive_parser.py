"""Unit tests for the Drive parser: classification (C5) and part-sort (C2)."""

from __future__ import annotations

from app.domain.models import MaterialKind
from app.services.drive_parser import (
    classify_file,
    lesson_number_from_title,
    parse_part_index,
    parse_recording_parts,
    walk_materials,
)

from tests.fixtures.drive_fixtures import (
    L2_PRES,
    L2_REC,
    L7_REC,
    L12_PRES,
    FakeDriveService,
)

_DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
_PDF = "application/pdf"


def test_classify_homework_by_name() -> None:
    assert classify_file("Python-intro-hw.docx", _DOCX) is MaterialKind.HOMEWORK
    assert classify_file("HW2 (2).docx", _DOCX) is MaterialKind.HOMEWORK
    assert classify_file("Homework- n8n agent.docx", _DOCX) is MaterialKind.HOMEWORK


def test_classify_slides_pdf_and_pptx() -> None:
    assert classify_file("lecture2.pptx (1).pdf", _PDF) is MaterialKind.SLIDES
    assert classify_file("deck.pptx", "x") is MaterialKind.SLIDES


def test_classify_code_by_parent_kind() -> None:
    assert classify_file("main.py", "text/x-python") is MaterialKind.CODE
    assert classify_file("notes.txt", "text/plain", parent_kind=MaterialKind.CODE) is (
        MaterialKind.CODE
    )


def test_classify_homework_by_parent_kind() -> None:
    assert classify_file("anything.docx", _DOCX, parent_kind=MaterialKind.HOMEWORK) is (
        MaterialKind.HOMEWORK
    )


def test_classify_other() -> None:
    assert classify_file("random.bin", "application/octet-stream") is MaterialKind.OTHER


def test_parse_part_index_tolerant() -> None:
    assert parse_part_index("part1.mp4") == 1
    assert parse_part_index("part 3.mp4") == 3
    assert parse_part_index("recording.mp4") is None


def test_lesson_number_from_title() -> None:
    assert lesson_number_from_title("Lesson 12") == 12
    assert lesson_number_from_title("Lesson 1") == 1
    assert lesson_number_from_title("intro") is None


def test_part_sort_handles_gap_and_naming() -> None:
    files = [
        {"id": "b", "title": "part 3.mp4", "mimeType": "video/mp4", "fileSize": "2"},
        {"id": "a", "title": "part1.mp4", "mimeType": "video/mp4", "fileSize": "1"},
    ]
    parts = parse_recording_parts(files)
    assert [p.part_index for p in parts] == [1, 3]  # sorted, gap preserved
    assert parts[0].size == 1


def test_part_sort_unknown_index_sorts_last() -> None:
    files = [
        {"id": "x", "title": "bonus.mp4", "mimeType": "video/mp4"},
        {"id": "y", "title": "part 1.mp4", "mimeType": "video/mp4"},
    ]
    parts = parse_recording_parts(files)
    assert parts[0].part_index == 1
    assert parts[1].part_index is None


def test_empty_recording_folder_yields_no_parts() -> None:
    assert parse_recording_parts([]) == []


async def test_walk_materials_flat() -> None:
    drive = FakeDriveService()
    materials = await walk_materials(drive, L2_PRES)
    kinds = sorted(m.kind for m in materials)
    # 3 homework docs + 1 slides pdf, none are videos.
    assert kinds.count(MaterialKind.HOMEWORK) == 3
    assert kinds.count(MaterialKind.SLIDES) == 1


async def test_walk_materials_nested() -> None:
    drive = FakeDriveService()
    materials = await walk_materials(drive, L12_PRES)
    by_kind = {m.kind for m in materials}
    assert MaterialKind.HOMEWORK in by_kind  # from HW/ subfolder
    assert MaterialKind.CODE in by_kind  # from code/ subfolder


async def test_walk_skips_recordings_and_empty() -> None:
    drive = FakeDriveService()
    assert await walk_materials(drive, L7_REC) == []
    # A recording folder has only videos -> no materials.
    assert await walk_materials(drive, L2_REC) == []
