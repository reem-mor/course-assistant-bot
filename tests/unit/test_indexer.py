"""Tests for the materials indexer and chunking."""

from __future__ import annotations

from typing import Any

import pytest
from app.services import indexer as indexer_mod
from app.services.indexer import MaterialsIndexer, chunk_text
from app.services.lesson_map_store import YamlLessonMapStore
from app.services.vectorstore_db import DbVectorStore

from tests.fixtures.drive_fixtures import FakeDriveService


class FakeEmbedder:
    def __init__(self) -> None:
        self.calls = 0

    async def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls += 1
        return [[1.0, 0.0, 0.0] for _ in texts]


def test_chunk_text_short() -> None:
    assert chunk_text("hello world") == ["hello world"]
    assert chunk_text("") == []


def test_chunk_text_long_overlaps() -> None:
    text = "word " * 500  # ~2500 chars
    chunks = chunk_text(text, size=800, overlap=100)
    assert len(chunks) > 1
    assert all(len(c) <= 800 for c in chunks)


async def test_reindex_indexes_materials(
    db_sessionmaker: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_extract(drive: object, file: dict[str, object]) -> str:
        return "python basics and data engineering content"

    monkeypatch.setattr(indexer_mod, "extract_text", fake_extract)

    store = DbVectorStore(db_sessionmaker)
    indexer = MaterialsIndexer(
        FakeDriveService(), YamlLessonMapStore().load(), FakeEmbedder(), store
    )
    count = await indexer.reindex()
    assert count > 0

    hits = await store.query(embedding=[1.0, 0.0, 0.0], top_k=3)
    assert hits
    assert hits[0].lesson_key is not None
