"""Summary feature handler (feature 6.2).

Wires the router's ``summarize`` intent to the SummaryService, formatting the outcome into
a localized reply. Slide-based summaries are the default; "deep" requests use the
transcript path (wired here, mocked in tests).
"""

from __future__ import annotations

from app.bot.router import Intent, IntentName
from app.core.i18n import Language, t
from app.core.logging import get_logger
from app.domain.lesson_map import LessonMap
from app.services.drive import try_get_drive_service
from app.services.lesson_map_store import YamlLessonMapStore
from app.services.llm import try_get_model_registry
from app.services.summaries import SummaryOutcome, SummaryService, SummaryStatus

_log = get_logger("bot.summary")


def _lesson_map() -> LessonMap:
    return YamlLessonMapStore().load()


def _summary_service() -> SummaryService | None:
    drive = try_get_drive_service()
    if drive is None:
        return None
    # Transcription is wired in Phase 5's worker; deep requests degrade to slides here.
    return SummaryService(drive, _lesson_map(), try_get_model_registry())


def format_summary(outcome: SummaryOutcome, language: Language) -> str:
    """Format a SummaryOutcome into a localized reply."""
    if outcome.status is SummaryStatus.LLM_UNAVAILABLE:
        return t("sum_llm_unavailable", language)
    if outcome.status is SummaryStatus.NO_MATERIALS:
        return t("sum_no_materials", language)
    header = t("sum_header", language).format(lesson=outcome.lesson_key or "?")
    return f"{header}\n\n{outcome.text}"


async def reply_for_summary_intent(intent: Intent, language: Language) -> str | None:
    """Produce a reply for the summarize intent, or None if not a summary intent."""
    if intent.name is not IntentName.SUMMARIZE:
        return None
    service = _summary_service()
    if service is None:
        return t("sum_llm_unavailable", language)
    _log.info("summarize_intent", lesson_ref=intent.lesson_ref, deep=intent.deep)
    outcome = await service.summarize_lesson(
        intent.lesson_ref, deep=intent.deep, language=language
    )
    return format_summary(outcome, language)
