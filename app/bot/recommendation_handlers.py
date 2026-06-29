"""Recommendations handler (feature 6.3).

Formats curated links + internal RAG hits (+ optional web results) into a short, ranked,
localized reply grouped as "From our course" and "Recommended reading".
"""

from __future__ import annotations

from app.bot.router import Intent, IntentName
from app.core.i18n import Language, t
from app.core.logging import get_logger
from app.core.settings import get_settings
from app.services.embeddings import get_embedder
from app.services.recommendations import (
    CourseRecommendationService,
    Recommendations,
)
from app.services.resources_catalog import get_resources_catalog
from app.services.vectorstore_db import get_vector_store

_log = get_logger("bot.recommendations")


def _service() -> CourseRecommendationService:
    """Build the recommendation service (patched in tests)."""
    settings = get_settings()
    return CourseRecommendationService(
        get_resources_catalog(),
        embedder=get_embedder(),
        store=get_vector_store(),
        web_search=None,  # optional provider; disabled in v1
        top_k=settings.rag_top_k,
    )


def format_recommendations(recs: Recommendations, language: Language) -> str:
    """Format a Recommendations bundle into a localized, grouped reply."""
    if recs.is_empty:
        return t("rec_none", language)
    lines: list[str] = []
    if recs.internal:
        lines.append(t("rec_header_course", language))
        for chunk in recs.internal:
            label = chunk.name or chunk.drive_file_id
            lines.append(f"- {label}: {chunk.view_url}")
    if recs.curated or recs.external:
        if lines:
            lines.append("")
        lines.append(t("rec_header_external", language))
        for curated in recs.curated:
            lines.append(f"- {curated.title}: {curated.url}")
        for ext in recs.external:
            lines.append(f"- {ext.title}: {ext.url}")
    return "\n".join(lines)


async def reply_for_materials_intent(intent: Intent, language: Language) -> str | None:
    """Produce a reply for the materials intent, or None if not a materials intent."""
    if intent.name is not IntentName.MATERIALS:
        return None
    topic = (intent.query or "").strip()
    if not topic:
        return t("rec_ask_topic", language)
    _log.info("materials_intent", topic=topic)
    recs = await _service().recommend(
        topic=topic, allow_web=get_settings().web_search_enabled, language=language
    )
    return format_recommendations(recs, language)
