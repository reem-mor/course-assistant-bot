"""Latest homework retrieval (feature 6.4).

Finds the newest homework document across the presentation/materials folders, classifying
files recursively and type-aware (C5). Returns the homework docs of the most recent lesson
(there may be several in one lesson - the user picks). The LLM 3-5 line requirements
summary is added in Phase 3 when the model layer exists.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.lesson_map import LessonMap
from app.domain.models import HomeworkAssignment, MaterialFile, MaterialKind
from app.services.drive import DriveService
from app.services.drive_parser import (
    file_id,
    file_name,
    is_folder,
    lesson_number_from_title,
    walk_materials,
)


@dataclass(frozen=True)
class LessonHomework:
    """All homework docs found in a single presentation lesson folder."""

    lesson_key: str
    assignments: list[HomeworkAssignment]


def _newest_modified(materials: list[MaterialFile]) -> str:
    """Return the max modifiedTime among materials (empty string if none known)."""
    return max((m.modified_time or "" for m in materials), default="")


class HomeworkService:
    """Locates homework documents in the presentations tree."""

    def __init__(self, drive: DriveService, lesson_map: LessonMap) -> None:
        self._drive = drive
        self._map = lesson_map

    async def _presentation_lesson_folders(self) -> list[dict[str, object]]:
        children = await self._drive.list_children(self._map.roots.presentations_folder)
        return [c for c in children if is_folder(c)]

    async def homework_in_folder(self, folder_id: str) -> list[MaterialFile]:
        """All homework-classified files within a presentation lesson folder (recursive)."""
        materials = await walk_materials(self._drive, folder_id)
        return [m for m in materials if m.kind is MaterialKind.HOMEWORK]

    async def latest(self) -> LessonHomework | None:
        """Find the lesson folder with the newest homework and return its HW docs.

        Folders are ranked by the newest homework ``modifiedTime``; when those are absent
        (as in some older folders), the highest 'Lesson N' number wins as a stable
        fallback.
        """
        folders = await self._presentation_lesson_folders()
        best: tuple[str, int, str, list[MaterialFile]] | None = None
        for folder in folders:
            name = file_name(folder)
            hw = await self.homework_in_folder(file_id(folder))
            if not hw:
                continue
            rank = (_newest_modified(hw), lesson_number_from_title(name) or 0)
            if best is None or rank > (best[0], best[1]):
                best = (rank[0], rank[1], name, hw)
        if best is None:
            return None
        _, _, lesson_name, materials = best
        assignments = [
            HomeworkAssignment(
                title=m.name,
                lesson_key=lesson_name,
                material=m,
                modified_time=m.modified_time,
            )
            for m in materials
        ]
        return LessonHomework(lesson_key=lesson_name, assignments=assignments)
