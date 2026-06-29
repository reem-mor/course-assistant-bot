"""Lesson summarization (feature 6.2).

Tiered source: slides/HW docs by default (fast, cheap), the recording transcript only for
explicit "deep / from the recording" requests or when no slides exist. Results are cached
by (lesson_key, source hash) so repeats and nightly precompute are instant.
"""

from __future__ import annotations

from collections.abc import MutableMapping
from dataclasses import dataclass
from enum import StrEnum

from app.core.cache import content_hash, make_ttl_cache
from app.core.logging import get_logger
from app.domain.lesson_map import LessonMap
from app.domain.models import MaterialKind
from app.graph.prompts import SUMMARIZER_SYSTEM
from app.services.content_extraction import extract_text
from app.services.drive import DriveService
from app.services.drive_parser import (
    file_id,
    file_name,
    is_folder,
    lesson_number_from_title,
    parse_recording_parts,
    walk_materials,
)
from app.services.llm import ModelRegistry, ModelRole
from app.services.transcription import TranscriptionService

_log = get_logger("summaries")

_MAX_SOURCE_CHARS = 12000
_SUMMARY_MAX_TOKENS = 1200

# Module-level cache shared across SummaryService instances so the nightly precompute job
# warms the same cache the chat handlers read.
_SHARED_SUMMARY_CACHE = make_ttl_cache()


class SummaryStatus(StrEnum):
    """Outcome of a summarization request."""

    OK = "ok"
    NO_MATERIALS = "no_materials"
    LLM_UNAVAILABLE = "llm_unavailable"


@dataclass(frozen=True)
class SummaryOutcome:
    """The result of a summarization request."""

    status: SummaryStatus
    lesson_key: str
    text: str = ""


class SummaryService:
    """Produces (and caches) lesson summaries from slides or transcripts."""

    def __init__(
        self,
        drive: DriveService,
        lesson_map: LessonMap,
        registry: ModelRegistry | None,
        *,
        transcription: TranscriptionService | None = None,
        cache: MutableMapping[str, str] | None = None,
    ) -> None:
        self._drive = drive
        self._map = lesson_map
        self._registry = registry
        self._transcription = transcription
        self._cache = cache if cache is not None else _SHARED_SUMMARY_CACHE

    async def _presentation_folder_for(self, lesson_ref: str | None) -> dict[str, object] | None:
        children = await self._drive.list_children(self._map.roots.presentations_folder)
        folders = [c for c in children if is_folder(c)]
        if not folders:
            return None
        if lesson_ref is not None and lesson_ref.isdigit():
            target = int(lesson_ref)
            for folder in folders:
                if lesson_number_from_title(file_name(folder)) == target:
                    return folder
            return None
        # No explicit lesson -> the highest-numbered presentation folder.
        return max(folders, key=lambda f: lesson_number_from_title(file_name(f)) or 0)

    async def _slide_text(self, folder_id: str) -> str:
        materials = await walk_materials(self._drive, folder_id)
        wanted = [m for m in materials if m.kind in (MaterialKind.SLIDES, MaterialKind.HOMEWORK)]
        chunks: list[str] = []
        for material in wanted:
            text = await extract_text(
                self._drive,
                {"id": material.drive_file_id, "name": material.name, "mimeType": ""},
            )
            if text.strip():
                chunks.append(f"## {material.name}\n{text}")
        return "\n\n".join(chunks)

    async def _transcript_text(self, lesson_ref: str | None) -> str:
        if self._transcription is None or lesson_ref is None or not lesson_ref.isdigit():
            return ""
        folder_id = self._map.recording_folder_by_label(int(lesson_ref))
        if folder_id is None:
            return ""
        children = await self._drive.list_children(folder_id)
        parts = parse_recording_parts(children)
        if not parts:
            return ""
        texts: list[str] = []
        for part in parts:
            texts.append(
                await self._transcription.transcribe(
                    drive_file_id=part.drive_file_id, modified_time=part.name
                )
            )
        return "\n".join(t for t in texts if t)

    async def summarize_lesson(
        self, lesson_ref: str | None, *, deep: bool, language: str
    ) -> SummaryOutcome:
        """Summarize a lesson from slides (default) or the recording transcript (deep)."""
        if self._registry is None:
            return SummaryOutcome(SummaryStatus.LLM_UNAVAILABLE, lesson_key=lesson_ref or "")

        folder = await self._presentation_folder_for(lesson_ref)
        lesson_key = file_name(folder) if folder else (lesson_ref or "")

        source = ""
        if deep:
            source = await self._transcript_text(lesson_ref)
        if not source and folder is not None:
            source = await self._slide_text(file_id(folder))
        if not source and not deep:
            source = await self._transcript_text(lesson_ref)
        if not source.strip():
            return SummaryOutcome(SummaryStatus.NO_MATERIALS, lesson_key=lesson_key)

        key = content_hash(lesson_key, language, source)
        cached = self._cache.get(key)
        if cached is not None:
            return SummaryOutcome(SummaryStatus.OK, lesson_key=lesson_key, text=cached)

        model = self._registry.for_role(ModelRole.SUMMARIZER)
        summary = await model.complete(
            system=SUMMARIZER_SYSTEM.format(language=language),
            prompt=source[:_MAX_SOURCE_CHARS],
            max_tokens=_SUMMARY_MAX_TOKENS,
        )
        self._cache[key] = summary
        _log.info("summary_generated", lesson_key=lesson_key, deep=deep)
        return SummaryOutcome(SummaryStatus.OK, lesson_key=lesson_key, text=summary)
