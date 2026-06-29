"""Tests for the recommendation service and reply formatting."""

from __future__ import annotations

from app.bot.recommendation_handlers import format_recommendations
from app.services.recommendations import (
    CourseRecommendationService,
    Recommendation,
    Recommendations,
)
from app.services.resources_catalog import get_resources_catalog
from app.services.vectorstore import RetrievedChunk


class FakeEmbedder:
    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0] for _ in texts]


class FakeStore:
    def __init__(self, chunks: list[RetrievedChunk]) -> None:
        self._chunks = chunks

    async def upsert(self, record: object, embedding: list[float]) -> None:  # pragma: no cover
        raise NotImplementedError

    async def query(self, *, embedding: list[float], top_k: int) -> list[RetrievedChunk]:
        return self._chunks[:top_k]

    async def clear(self) -> None:  # pragma: no cover
        raise NotImplementedError


def _chunk(file_id: str) -> RetrievedChunk:
    return RetrievedChunk(
        text="t", score=0.9, drive_file_id=file_id,
        view_url=f"https://drive/{file_id}", name=f"slides-{file_id}",
    )


async def test_recommend_combines_curated_and_internal() -> None:
    store = FakeStore([_chunk("f1"), _chunk("f1"), _chunk("f2")])
    service = CourseRecommendationService(
        get_resources_catalog(), embedder=FakeEmbedder(), store=store, top_k=4
    )
    recs = await service.recommend(topic="docker", allow_web=False, language="en")
    assert recs.curated  # docker is a curated topic
    # Internal chunks deduped by drive_file_id.
    assert {c.drive_file_id for c in recs.internal} == {"f1", "f2"}
    assert recs.external == []


async def test_recommend_unknown_topic_without_rag_is_empty() -> None:
    service = CourseRecommendationService(get_resources_catalog())
    recs = await service.recommend(topic="basket weaving", allow_web=False, language="en")
    assert recs.is_empty


def test_format_groups_sections() -> None:
    recs = Recommendations(
        internal=[_chunk("f1")],
        curated=get_resources_catalog().lookup("docker"),
        external=[Recommendation(title="Blog", url="https://x")],
    )
    text = format_recommendations(recs, "en")
    assert "From our course:" in text
    assert "Recommended reading:" in text
    assert "slides-f1" in text
    assert "Blog: https://x" in text


def test_format_empty() -> None:
    assert "couldn't find" in format_recommendations(Recommendations(), "en")
