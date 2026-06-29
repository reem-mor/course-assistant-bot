"""Unit tests for content extraction dispatch by mime/extension."""

from __future__ import annotations

import pytest
from app.services import content_extraction
from app.services.content_extraction import extract_text

from tests.fixtures.drive_fixtures import FakeDriveService

_DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
_PPTX = "application/vnd.openxmlformats-officedocument.presentationml.presentation"


async def test_google_native_uses_export() -> None:
    drive = FakeDriveService()
    file = {"id": "doc1", "name": "notes", "mimeType": "application/vnd.google-apps.document"}
    text = await extract_text(drive, file)
    assert "fake content for doc1" in text


async def test_pdf_dispatch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(content_extraction, "_extract_pdf", lambda data: "PDF TEXT")
    drive = FakeDriveService()
    file = {"id": "p", "name": "lecture.pdf", "mimeType": "application/pdf"}
    assert await extract_text(drive, file) == "PDF TEXT"


async def test_docx_dispatch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(content_extraction, "_extract_docx", lambda data: "DOCX TEXT")
    drive = FakeDriveService()
    file = {"id": "d", "name": "hw.docx", "mimeType": _DOCX}
    assert await extract_text(drive, file) == "DOCX TEXT"


async def test_pptx_dispatch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(content_extraction, "_extract_pptx", lambda data: "PPTX TEXT")
    drive = FakeDriveService()
    file = {"id": "s", "name": "deck.pptx", "mimeType": _PPTX}
    assert await extract_text(drive, file) == "PPTX TEXT"


async def test_oversized_file_skipped() -> None:
    drive = FakeDriveService()
    file = {"id": "big", "name": "huge.pdf", "mimeType": "application/pdf",
            "size": str(50 * 1024 * 1024)}
    assert await extract_text(drive, file) == ""


async def test_extraction_failure_is_swallowed(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(data: bytes) -> str:
        raise ValueError("corrupt")

    monkeypatch.setattr(content_extraction, "_extract_pdf", boom)
    drive = FakeDriveService()
    file = {"id": "p", "name": "bad.pdf", "mimeType": "application/pdf"}
    assert await extract_text(drive, file) == ""
