"""Drive parsing helpers: type-aware classification (C5) and part-sort (C2).

Tolerant of the real-world Drive quirks: inconsistent part naming (`part1.mp4` vs
`part 3.mp4`), gaps in part numbers, flat vs nested presentation folders, and the two
Drive field-name conventions (`name`/`title`, `size`/`fileSize`).
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from app.domain.models import (
    MaterialFile,
    MaterialKind,
    RecordingPart,
    drive_view_url,
)

if TYPE_CHECKING:
    from app.services.drive import DriveService

_FOLDER_MIME = "application/vnd.google-apps.folder"
_PART_RE = re.compile(r"part\s*(\d+)", re.IGNORECASE)
_TRAILING_INT_RE = re.compile(r"(\d+)")
_HOMEWORK_RE = re.compile(r"\bhw|homework|assignment|מטלה|שיעורי\s*בית", re.IGNORECASE)
_CODE_EXTS = (".py", ".ipynb", ".js", ".ts", ".java", ".cpp", ".c", ".go", ".rs", ".sql")
_SLIDE_EXTS = (".pptx", ".ppt", ".pdf", ".key")
_SLIDE_MIMES = (
    "application/vnd.google-apps.presentation",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "application/pdf",
)
_VIDEO_EXTS = (".mp4", ".mov", ".mkv", ".avi", ".m4v")


# --- tolerant field accessors -------------------------------------------------
def file_id(f: dict[str, Any]) -> str:
    return str(f["id"])


def file_name(f: dict[str, Any]) -> str:
    return str(f.get("name") or f.get("title") or "")


def file_mime(f: dict[str, Any]) -> str:
    return str(f.get("mimeType") or "")


def file_size(f: dict[str, Any]) -> int | None:
    raw = f.get("size") or f.get("fileSize")
    return int(raw) if raw is not None else None


def file_modified(f: dict[str, Any]) -> str | None:
    value = f.get("modifiedTime")
    return str(value) if value is not None else None


def is_folder(f: dict[str, Any]) -> bool:
    return file_mime(f) == _FOLDER_MIME


def is_video(f: dict[str, Any]) -> bool:
    """True if a file looks like a playable video (by mime or extension)."""
    if file_mime(f).startswith("video/"):
        return True
    return file_name(f).lower().endswith(_VIDEO_EXTS)


def folder_kind_from_name(name: str) -> MaterialKind | None:
    """Infer a kind from a subfolder name (e.g. 'HW/' -> homework, 'code/' -> code)."""
    lowered = name.strip().lower()
    if lowered in {"hw", "homework"} or _HOMEWORK_RE.search(name):
        return MaterialKind.HOMEWORK
    if lowered == "code":
        return MaterialKind.CODE
    return None


def classify_file(
    name: str, mime: str, *, parent_kind: MaterialKind | None = None
) -> MaterialKind:
    """Classify a file by filename heuristics + mime, honoring its parent folder kind."""
    lowered = name.lower()
    if parent_kind is MaterialKind.HOMEWORK or _HOMEWORK_RE.search(name):
        return MaterialKind.HOMEWORK
    if parent_kind is MaterialKind.CODE or lowered.endswith(_CODE_EXTS):
        return MaterialKind.CODE
    if mime in _SLIDE_MIMES or lowered.endswith(_SLIDE_EXTS):
        return MaterialKind.SLIDES
    return MaterialKind.OTHER


def lesson_number_from_title(name: str) -> int | None:
    """Extract the trailing/first integer from a folder title like 'Lesson 12'."""
    match = _TRAILING_INT_RE.search(name)
    return int(match.group(1)) if match else None


def parse_part_index(name: str) -> int | None:
    """Extract a part number from a recording filename, or None if absent (C2)."""
    match = _PART_RE.search(name)
    return int(match.group(1)) if match else None


def parse_recording_parts(files: list[dict[str, Any]]) -> list[RecordingPart]:
    """Build a tolerant, natural-sorted list of recording parts (gaps preserved)."""
    parts = [
        RecordingPart(
            drive_file_id=file_id(f),
            part_index=parse_part_index(file_name(f)),
            name=file_name(f),
            size=file_size(f),
            view_url=drive_view_url(file_id(f)),
        )
        for f in files
        if is_video(f)
    ]
    # Parts with a parsed index sort first by that index; unknown indices sort last.
    return sorted(parts, key=lambda p: (p.part_index is None, p.part_index or 0, p.name))


async def walk_all_files(
    service: DriveService, folder_id: str
) -> list[dict[str, Any]]:
    """Recursively enumerate every non-folder file under a tree (for the Drive watcher).

    Returns normalized dicts with id, name, mimeType, modifiedTime, and parent folder id.
    """
    found: list[dict[str, Any]] = []
    children = await service.list_children(folder_id)
    for child in children:
        if is_folder(child):
            found.extend(await walk_all_files(service, file_id(child)))
            continue
        found.append(
            {
                "id": file_id(child),
                "name": file_name(child),
                "mimeType": file_mime(child),
                "modifiedTime": file_modified(child),
                "parent": folder_id,
            }
        )
    return found


async def walk_materials(
    service: DriveService, folder_id: str, *, parent_kind: MaterialKind | None = None
) -> list[MaterialFile]:
    """Recursively collect non-recording materials from a folder tree (C5)."""
    materials: list[MaterialFile] = []
    children = await service.list_children(folder_id)
    for child in children:
        name = file_name(child)
        if is_folder(child):
            sub_kind = folder_kind_from_name(name) or parent_kind
            materials.extend(
                await walk_materials(service, file_id(child), parent_kind=sub_kind)
            )
            continue
        if is_video(child):
            continue  # recordings are handled separately, never as materials
        kind = classify_file(name, file_mime(child), parent_kind=parent_kind)
        materials.append(
            MaterialFile(
                kind=kind,
                name=name,
                drive_file_id=file_id(child),
                view_url=drive_view_url(file_id(child)),
                modified_time=file_modified(child),
            )
        )
    return materials
