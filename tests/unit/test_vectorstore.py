"""Tests for the DB-backed vector store and cosine ranking."""

from __future__ import annotations

from typing import Any

from app.services.vectorstore import ChunkRecord
from app.services.vectorstore_db import DbVectorStore, cosine_similarity


def test_cosine_similarity() -> None:
    assert cosine_similarity([1.0, 0.0], [1.0, 0.0]) == 1.0
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == 0.0
    assert cosine_similarity([], [1.0]) == 0.0


def _record(chunk_id: str, file_id: str) -> ChunkRecord:
    return ChunkRecord(
        chunk_id=chunk_id, drive_file_id=file_id, name=f"file-{file_id}",
        view_url=f"https://drive/{file_id}", text=f"text {chunk_id}", lesson_key="Lesson 1",
    )


async def test_upsert_and_rank(db_sessionmaker: Any) -> None:
    store = DbVectorStore(db_sessionmaker)
    await store.upsert(_record("a", "fA"), [1.0, 0.0])
    await store.upsert(_record("b", "fB"), [0.0, 1.0])

    top = await store.query(embedding=[1.0, 0.0], top_k=2)
    assert top[0].drive_file_id == "fA"
    assert top[0].score > top[1].score
    assert top[0].name == "file-fA"


async def test_upsert_updates_existing(db_sessionmaker: Any) -> None:
    store = DbVectorStore(db_sessionmaker)
    await store.upsert(_record("a", "fA"), [1.0, 0.0])
    await store.upsert(_record("a", "fA"), [0.0, 1.0])  # same chunk_id, new vector
    top = await store.query(embedding=[0.0, 1.0], top_k=1)
    assert len(top) == 1
    assert top[0].score == 1.0


async def test_clear(db_sessionmaker: Any) -> None:
    store = DbVectorStore(db_sessionmaker)
    await store.upsert(_record("a", "fA"), [1.0, 0.0])
    await store.clear()
    assert await store.query(embedding=[1.0, 0.0], top_k=5) == []
