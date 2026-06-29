"""Nightly precompute job (Section 10).

Warms the shared summary cache for lessons that have linked presentation folders, so
user-facing summaries are instant. Uses the same ``SummaryService`` (and shared cache) the
chat handlers use. No-ops gracefully when Drive or an LLM provider isn't configured.
"""

from __future__ import annotations

from app.core.logging import get_logger
from app.domain.lesson_map import LessonMap
from app.services.drive import DriveService
from app.services.drive_parser import file_name, is_folder, lesson_number_from_title
from app.services.llm import ModelRegistry
from app.services.summaries import SummaryService

_log = get_logger("worker.precompute")


class Precomputer:
    """Precomputes (caches) slide summaries for known presentation lessons."""

    def __init__(
        self, drive: DriveService, lesson_map: LessonMap, registry: ModelRegistry
    ) -> None:
        self._drive = drive
        self._map = lesson_map
        self._registry = registry

    async def run_once(self) -> int:
        """Warm summaries for each presentation lesson. Returns lessons precomputed."""
        service = SummaryService(self._drive, self._map, self._registry)
        children = await self._drive.list_children(self._map.roots.presentations_folder)
        done = 0
        for folder in children:
            if not is_folder(folder):
                continue
            number = lesson_number_from_title(file_name(folder))
            if number is None:
                continue
            try:
                outcome = await service.summarize_lesson(
                    str(number), deep=False, language="he"
                )
            except Exception:  # one bad lesson must not abort the whole pass
                _log.exception("precompute_lesson_failed", lesson=number)
                continue
            if outcome.text:
                done += 1
        _log.info("precompute_complete", lessons=done)
        return done
