"""Tests for the curated resources catalog."""

from __future__ import annotations

from app.services.resources_catalog import get_resources_catalog


def test_lookup_by_key() -> None:
    catalog = get_resources_catalog()
    docker = catalog.lookup("docker")
    assert docker
    assert any("docker.com" in r.url for r in docker)


def test_lookup_by_alias() -> None:
    catalog = get_resources_catalog()
    # "embeddings" is an alias of the rag topic.
    rag = catalog.lookup("embeddings")
    assert rag
    assert any("rag" in r.url.lower() or "embedding" in r.url.lower() for r in rag)


def test_lookup_phrase_contains_topic() -> None:
    catalog = get_resources_catalog()
    assert catalog.lookup("what should I study about docker")  # substring match


def test_unknown_topic_returns_empty() -> None:
    assert get_resources_catalog().lookup("underwater basket weaving") == []
