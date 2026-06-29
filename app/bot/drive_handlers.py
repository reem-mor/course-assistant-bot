"""Drive feature handlers: recordings (6.6) and latest homework (6.4).

Formats service results into localized he/en replies. Recordings are always presented as
Drive view links with per-part labels and a transparent note when parts are missing (C2);
empty/unlinked folders are reported plainly (C1/C3). Pure formatting is separated from
service wiring so it is unit-testable.
"""

from __future__ import annotations

from app.bot.router import Intent, IntentName, Scope
from app.core.i18n import Language, t
from app.core.logging import get_logger
from app.domain.lesson_map import LessonMap
from app.services.drive import try_get_drive_service
from app.services.homework import HomeworkService, LessonHomework
from app.services.lesson_map_store import YamlLessonMapStore
from app.services.recordings import RecordingResult, RecordingsService
from app.services.schedule import get_schedule_service

_log = get_logger("bot.drive")


def _lesson_map() -> LessonMap:
    return YamlLessonMapStore().load()


def _recordings_service() -> RecordingsService | None:
    drive = try_get_drive_service()
    if drive is None:
        return None
    return RecordingsService(drive, _lesson_map(), get_schedule_service())


def _homework_service() -> HomeworkService | None:
    drive = try_get_drive_service()
    if drive is None:
        return None
    return HomeworkService(drive, _lesson_map())


def _has_gap(result: RecordingResult) -> bool:
    """True if part numbers are non-contiguous or any part lacks a number (C2)."""
    indices = [p.part_index for p in result.parts if p.part_index is not None]
    if any(p.part_index is None for p in result.parts):
        return True
    if not indices:
        return False
    return (max(indices) - min(indices) + 1) != len(set(indices))


def format_recording_result(result: RecordingResult, language: Language) -> str:
    """Format a single lesson's recording result as Drive links (C4)."""
    if not result.linked:
        return t("rec_not_linked", language)
    if result.empty:
        return t("rec_not_uploaded", language)
    lines = [t("rec_header", language).format(label=result.label)]
    for part in result.parts:
        lines.append(
            t("rec_part_line", language).format(n=part.label_number, url=part.view_url)
        )
    if _has_gap(result):
        lines.append(t("rec_gap_note", language))
    return "\n".join(lines)


def format_all_recordings(results: list[RecordingResult], language: Language) -> str:
    """Format the 'all recordings' overview (label -> count / not uploaded)."""
    lines = [t("rec_all_header", language)]
    for result in results:
        if result.parts:
            lines.append(
                t("rec_all_item_count", language).format(
                    label=result.label, n=len(result.parts)
                )
            )
        else:
            lines.append(t("rec_all_item_empty", language).format(label=result.label))
    return "\n".join(lines)


def format_homework(lesson_hw: LessonHomework, language: Language) -> str:
    """Format the latest-homework reply, listing all HW docs in the lesson."""
    lines = [t("hw_header", language).format(lesson=lesson_hw.lesson_key)]
    if len(lesson_hw.assignments) > 1:
        lines.append(t("hw_multiple_note", language))
    for assignment in lesson_hw.assignments:
        lines.append(
            t("hw_item", language).format(
                title=assignment.title, url=assignment.material.view_url
            )
        )
    return "\n".join(lines)


async def _reply_recording(intent: Intent, language: Language) -> str:
    service = _recordings_service()
    if service is None:
        return t("drive_not_configured", language)
    if intent.scope is Scope.ALL:
        return format_all_recordings(await service.all_with_recordings(), language)
    if intent.scope is Scope.SPECIFIC and intent.lesson_ref is not None:
        result = await service.by_alex_label(int(intent.lesson_ref))
        return format_recording_result(result, language)
    last = await service.last()
    if last is None:
        return t("rec_last_none", language)
    return format_recording_result(last, language)


async def _reply_homework(language: Language) -> str:
    service = _homework_service()
    if service is None:
        return t("drive_not_configured", language)
    lesson_hw = await service.latest()
    if lesson_hw is None:
        return t("hw_none", language)
    return format_homework(lesson_hw, language)


async def reply_for_drive_intent(intent: Intent, language: Language) -> str | None:
    """Produce a reply for recording/homework intents, or None if not a drive intent."""
    if intent.name is IntentName.RECORDING:
        _log.info("recording_intent", scope=intent.scope, lesson_ref=intent.lesson_ref)
        return await _reply_recording(intent, language)
    if intent.name is IntentName.HOMEWORK_LATEST:
        _log.info("homework_intent")
        return await _reply_homework(language)
    return None
