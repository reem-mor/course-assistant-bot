"""Real-shaped Drive fixtures (Appendix D) and a fake DriveService.

Uses the exact field-name quirks from the live Drive API (``title``/``fileSize``) so the
tolerant accessors in ``drive_parser`` are exercised. No live calls.
"""

from __future__ import annotations

from typing import Any

# --- Folder ids (from grounded facts + Appendix C/D) -------------------------
RECORDINGS_FOLDER = "1bVrDPbVxsiSTyguWYFEVjovgYbDh9469"
PRESENTATIONS_FOLDER = "1JpwQBI8wi3J5OigcMbAG8YRKLLzXIf48"

L1_REC = "14J5qQTx5pz_aMtiKDcz3ohgElp9A8tHd"
L2_REC = "1Fr2dFnA4eOScaOww9n860pe0sOx6YgnT"
L3_REC = "1962um0GLot2fnzVjnNEqjE1GuDjCIOVJ"
L7_REC = "1HQv3mIQPqBXVgGWQN3XD2Yf3Tl26Dqy8"  # empty (C3)

L2_PRES = "12f7hoIT754XmfFVajjLSnxCkIGVf5VZf"  # flat (C5)
L12_PRES = "1hSC_0pi3MaF8Z81K049Ws0PWY4Mnk0GR"  # nested (C5)
L12_HW = "1Pm2XV_q8I2vk6FfuLshEkdtc7Iweh3b_"
L12_CODE = "1pSbg8Ge0YU0elndXiK9SPr2yqqlfgV7L"

_FOLDER = "application/vnd.google-apps.folder"
_DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
_PDF = "application/pdf"
_VIDEO = "video/mp4"

# --- The fake Drive tree: folder id -> children (Appendix D shapes) ----------
FAKE_TREE: dict[str, list[dict[str, Any]]] = {
    # Lesson 1 recording: a single part.
    L1_REC: [
        {"id": "L1p1", "title": "part 1.mp4", "mimeType": _VIDEO, "fileSize": "98000000"},
    ],
    # Lesson 2 recording: gap + inconsistent naming (part1.mp4 + part 3.mp4).
    L2_REC: [
        {"id": "14Nfn3", "title": "part1.mp4", "mimeType": _VIDEO, "fileSize": "288388677"},
        {"id": "1AIkxU", "title": "part 3.mp4", "mimeType": _VIDEO, "fileSize": "145174810"},
    ],
    # Lesson 3 recording: also part 1 + part 3.
    L3_REC: [
        {"id": "L3p1", "title": "part 1.mp4", "mimeType": _VIDEO, "fileSize": "120000000"},
        {"id": "L3p3", "title": "part 3.mp4", "mimeType": _VIDEO, "fileSize": "130000000"},
    ],
    # Lesson 7 recording: empty (C3) -> not present below means [].
    L7_REC: [],
    # Presentations parent: one flat lesson, one nested lesson.
    PRESENTATIONS_FOLDER: [
        {"id": L2_PRES, "title": "Lesson 2", "mimeType": _FOLDER},
        {"id": L12_PRES, "title": "Lesson 12", "mimeType": _FOLDER},
    ],
    # Lesson 2 presentation: flat, multiple HW + a lecture pdf.
    L2_PRES: [
        {"id": "1wjI7D", "title": "Jupyter-intro-hw.docx", "mimeType": _DOCX,
         "modifiedTime": "2026-05-06T09:00:00Z"},
        {"id": "1qah24", "title": "Python-intro-hw.docx", "mimeType": _DOCX,
         "modifiedTime": "2026-05-06T09:05:00Z"},
        {"id": "1WQpSp", "title": "HW2 (2).docx", "mimeType": _DOCX,
         "modifiedTime": "2026-05-06T09:10:00Z"},
        {"id": "1XEx-Q", "title": "lecture2.pptx (1).pdf", "mimeType": _PDF,
         "modifiedTime": "2026-05-06T09:15:00Z"},
    ],
    # Lesson 12 presentation: nested HW/ + code/.
    L12_PRES: [
        {"id": L12_HW, "title": "HW", "mimeType": _FOLDER},
        {"id": L12_CODE, "title": "code", "mimeType": _FOLDER},
    ],
    L12_HW: [
        {"id": "1Mfaf0", "title": "Homework- Build an n8n AI Customer Support Agent.docx",
         "mimeType": _DOCX, "modifiedTime": "2026-06-17T10:00:00Z"},
    ],
    L12_CODE: [
        {"id": "codepy", "title": "main.py", "mimeType": "text/x-python"},
    ],
}


class FakeDriveService:
    """A DriveService returning canned Appendix D payloads. No live calls."""

    def __init__(self, tree: dict[str, list[dict[str, Any]]] | None = None) -> None:
        self._tree = tree if tree is not None else FAKE_TREE

    async def list_children(self, folder_id: str) -> list[dict[str, Any]]:
        return list(self._tree.get(folder_id, []))

    async def read_file_content(self, file_id: str) -> str:
        return f"fake content for {file_id}"

    async def download_file(self, file_id: str) -> bytes:
        return f"fake bytes for {file_id}".encode()
