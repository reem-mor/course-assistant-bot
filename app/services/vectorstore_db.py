"""DB-backed vector store (Phase 6).

Stores chunk embeddings as JSON in the ``materials_index`` table and ranks by cosine
similarity in Python. This runs identically on SQLite (dev) and Supabase Postgres (prod);
a pgvector-accelerated implementation is a Phase 7 optimization behind the same interface.
For a class-sized corpus, brute-force cosine is more than adequate.
"""

from __future__ import annotations

import json
import math

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.repo.db import get_sessionmaker
from app.repo.models import MaterialChunk
from app.services.vectorstore import ChunkRecord, RetrievedChunk


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Cosine similarity between two equal-length vectors (0.0 if degenerate)."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


class DbVectorStore:
    """VectorStore backed by the ``materials_index`` table."""

    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession]) -> None:
        self._sm = sessionmaker

    async def upsert(self, record: ChunkRecord, embedding: list[float]) -> None:
        async with self._sm() as session, session.begin():
            existing = await session.get(MaterialChunk, record.chunk_id)
            payload = json.dumps(embedding)
            if existing is None:
                session.add(
                    MaterialChunk(
                        chunk_id=record.chunk_id,
                        drive_file_id=record.drive_file_id,
                        lesson_key=record.lesson_key,
                        name=record.name,
                        view_url=record.view_url,
                        text=record.text,
                        embedding=payload,
                    )
                )
            else:
                existing.text = record.text
                existing.embedding = payload
                existing.name = record.name
                existing.view_url = record.view_url
                existing.lesson_key = record.lesson_key

    async def query(self, *, embedding: list[float], top_k: int) -> list[RetrievedChunk]:
        async with self._sm() as session:
            result = await session.execute(select(MaterialChunk))
            rows = result.scalars().all()
        scored = [
            (
                cosine_similarity(embedding, json.loads(row.embedding)),
                row,
            )
            for row in rows
        ]
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [
            RetrievedChunk(
                text=row.text,
                score=score,
                drive_file_id=row.drive_file_id,
                view_url=row.view_url,
                name=row.name,
                lesson_key=row.lesson_key,
            )
            for score, row in scored[:top_k]
        ]

    async def clear(self) -> None:
        async with self._sm() as session, session.begin():
            await session.execute(delete(MaterialChunk))


def get_vector_store() -> DbVectorStore:
    """Return a DB-backed vector store using the shared session factory."""
    return DbVectorStore(get_sessionmaker())
