"""Recommendations (feature 6.3).

Combines curated ``resources.yaml`` topic->links, RAG over indexed course materials, and an
optional web-search tool (disabled by default). Web search is behind an interface so a
provider can be plugged in later without touching callers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from app.services.resources_catalog import CuratedResource, ResourcesCatalog
from app.services.vectorstore import Embedder, RetrievedChunk, VectorStore


@dataclass(frozen=True, slots=True)
class Recommendation:
    """A single recommended external resource."""

    title: str
    url: str
    source: str = "external"


@dataclass(frozen=True)
class Recommendations:
    """The combined recommendation result for a topic."""

    internal: list[RetrievedChunk] = field(default_factory=list)
    curated: list[CuratedResource] = field(default_factory=list)
    external: list[Recommendation] = field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return not (self.internal or self.curated or self.external)


@runtime_checkable
class WebSearch(Protocol):
    """Optional external web-search provider."""

    async def search(self, query: str, *, limit: int) -> list[Recommendation]: ...


class CourseRecommendationService:
    """Recommends learning materials: curated links + RAG over course materials + web."""

    def __init__(
        self,
        catalog: ResourcesCatalog,
        *,
        embedder: Embedder | None = None,
        store: VectorStore | None = None,
        web_search: WebSearch | None = None,
        top_k: int = 4,
    ) -> None:
        self._catalog = catalog
        self._embedder = embedder
        self._store = store
        self._web = web_search
        self._top_k = top_k

    async def _internal(self, topic: str) -> list[RetrievedChunk]:
        if self._embedder is None or self._store is None:
            return []
        vectors = await self._embedder.embed([topic])
        if not vectors:
            return []
        chunks = await self._store.query(embedding=vectors[0], top_k=self._top_k)
        # Deduplicate by source file, preserving the highest-scoring chunk per file.
        seen: set[str] = set()
        unique: list[RetrievedChunk] = []
        for chunk in chunks:
            if chunk.drive_file_id in seen:
                continue
            seen.add(chunk.drive_file_id)
            unique.append(chunk)
        return unique

    async def recommend(
        self, *, topic: str, allow_web: bool, language: str
    ) -> Recommendations:
        """Return curated + internal (RAG) + optional external recommendations."""
        curated = self._catalog.lookup(topic)
        internal = await self._internal(topic)
        external: list[Recommendation] = []
        if allow_web and self._web is not None:
            external = await self._web.search(topic, limit=3)
        return Recommendations(internal=internal, curated=curated, external=external)


@runtime_checkable
class RecommendationService(Protocol):
    """Recommends learning materials for a topic or lesson."""

    async def recommend(
        self, *, topic: str, allow_web: bool, language: str
    ) -> Recommendations: ...
