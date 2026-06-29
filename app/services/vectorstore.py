"""Vector store + embedder interfaces.

Primary store target: Supabase Postgres (+ pgvector accel later); dev fallback: SQLite.
Phase 6 implements a DB-backed store (embeddings stored as JSON, cosine in Python) behind
this interface so it runs identically on both; pgvector indexing is a Phase 7 optimization.
Embeddings via ``text-embedding-3-small``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class RetrievedChunk:
    """A retrieved material chunk with its similarity score and source link."""

    text: str
    score: float
    drive_file_id: str
    view_url: str
    name: str = ""
    lesson_key: str | None = None


@dataclass(frozen=True, slots=True)
class ChunkRecord:
    """A material chunk to index."""

    chunk_id: str
    drive_file_id: str
    name: str
    view_url: str
    text: str
    lesson_key: str | None = None
    metadata: dict[str, str] = field(default_factory=dict)


@runtime_checkable
class Embedder(Protocol):
    """Produces embedding vectors for text."""

    async def embed(self, texts: list[str]) -> list[list[float]]: ...


@runtime_checkable
class VectorStore(Protocol):
    """Stores and retrieves embedded course-material chunks."""

    async def upsert(self, record: ChunkRecord, embedding: list[float]) -> None:
        """Insert or update a chunk and its embedding."""
        ...

    async def query(self, *, embedding: list[float], top_k: int) -> list[RetrievedChunk]:
        """Return the top-k most similar chunks for a query embedding."""
        ...

    async def clear(self) -> None:
        """Remove all indexed chunks (used by /reindex)."""
        ...
