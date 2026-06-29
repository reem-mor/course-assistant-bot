"""Drive watcher (feature 6.7).

Periodically enumerates the Recordings + Presentations trees, diffs each file's
``(id, modifiedTime)`` against ``drive_state``, and broadcasts genuinely new/changed files
to subscribers. The first ever run seeds ``drive_state`` silently so the entire backlog is
not broadcast. Idempotency is enforced by ``broadcast_log`` keyed on ``(file_id, mtime)``.
"""

from __future__ import annotations

from typing import Any

from app.core.i18n import DEFAULT_LANGUAGE, t
from app.core.logging import get_logger
from app.domain.lesson_map import LessonMap
from app.domain.models import MaterialKind, drive_view_url
from app.repo.repositories import DriveStateRepo
from app.services.drive import DriveService
from app.services.drive_parser import classify_file, is_video, walk_all_files
from app.services.notifier import Notifier

_log = get_logger("worker.drive_watcher")

_KIND_LABEL_KEY = {
    "recording": "kind_recording",
    MaterialKind.SLIDES: "kind_slides",
    MaterialKind.HOMEWORK: "kind_homework",
    MaterialKind.CODE: "kind_code",
    MaterialKind.OTHER: "kind_other",
}


class DriveWatcher:
    """Detects new/changed Drive files and broadcasts them once."""

    def __init__(
        self,
        drive: DriveService,
        lesson_map: LessonMap,
        notifier: Notifier,
        drive_state: DriveStateRepo,
    ) -> None:
        self._drive = drive
        self._map = lesson_map
        self._notifier = notifier
        self._state = drive_state

    def _classify(self, file: dict[str, Any]) -> str | MaterialKind:
        if is_video(file):
            return "recording"
        return classify_file(file.get("name", ""), file.get("mimeType", ""))

    def _lesson_for_parent(self, parent: str | None) -> str | None:
        """Best-effort: map a recording folder id back to Alex's 'Lesson N' label."""
        if parent is None:
            return None
        for label, folder_id in self._map.recordings_by_alex_label.items():
            if folder_id == parent:
                return f"Lesson {label}"
        return None

    async def _enumerate(self) -> list[dict[str, Any]]:
        files: list[dict[str, Any]] = []
        for root in (
            self._map.roots.recordings_folder,
            self._map.roots.presentations_folder,
        ):
            files.extend(await walk_all_files(self._drive, root))
        return files

    def _format_message(self, file: dict[str, Any], kind: str | MaterialKind) -> str:
        lesson = self._lesson_for_parent(file.get("parent"))
        lesson_suffix = (
            t("notify_lesson_suffix", DEFAULT_LANGUAGE).format(lesson=lesson)
            if lesson
            else ""
        )
        kind_label = t(_KIND_LABEL_KEY.get(kind, "kind_other"), DEFAULT_LANGUAGE)
        return t("notify_new_material", DEFAULT_LANGUAGE).format(
            kind=kind_label,
            lesson=lesson_suffix,
            name=file.get("name", ""),
            link=drive_view_url(str(file.get("id"))),
        )

    async def run_once(self) -> int:
        """Run a single watch pass. Returns the number of broadcasts sent."""
        files = await self._enumerate()
        first_run = await self._state.is_empty()
        known = await self._state.known_modified()

        broadcasts = 0
        for file in files:
            file_id = str(file.get("id"))
            mtime = file.get("modifiedTime")
            kind = self._classify(file)
            kind_str = kind.value if isinstance(kind, MaterialKind) else kind

            is_new_or_changed = file_id not in known or known.get(file_id) != mtime
            if not first_run and is_new_or_changed:
                key = f"{file_id}:{mtime}"
                result = await self._notifier.broadcast(
                    idempotency_key=key, message=self._format_message(file, kind)
                )
                if result.sent or result.failed:
                    broadcasts += 1

            await self._state.upsert(
                file_id=file_id,
                parent=file.get("parent"),
                modified_time=mtime,
                kind=kind_str,
                lesson_key=self._lesson_for_parent(file.get("parent")),
            )

        if first_run:
            _log.info("drive_watcher_seeded", files=len(files))
        else:
            _log.info("drive_watcher_pass", files=len(files), broadcasts=broadcasts)
        return broadcasts
