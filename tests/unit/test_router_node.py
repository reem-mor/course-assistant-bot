"""Unit tests for the LLM router fallback node (defensive JSON parsing)."""

from __future__ import annotations

import pytest
from app.bot.router import IntentName, Scope
from app.graph import router_node
from app.graph.router_node import classify, parse_router_json


def test_parse_valid_json() -> None:
    raw = '{"intent": "schedule", "scope": "next", "lesson_ref": null, "language": "en"}'
    intent = parse_router_json(raw)
    assert intent is not None
    assert intent.name is IntentName.SCHEDULE
    assert intent.scope is Scope.NEXT


def test_parse_json_with_surrounding_prose() -> None:
    raw = 'Sure!\n```json\n{"intent": "recording", "scope": "all"}\n```'
    intent = parse_router_json(raw)
    assert intent is not None
    assert intent.name is IntentName.RECORDING
    assert intent.scope is Scope.ALL


def test_parse_lesson_ref_coerced_to_str() -> None:
    intent = parse_router_json('{"intent": "summarize", "lesson_ref": 5}')
    assert intent is not None
    assert intent.name is IntentName.SUMMARIZE
    assert intent.lesson_ref == "5"


def test_parse_malformed_returns_none() -> None:
    assert parse_router_json("not json at all") is None
    assert parse_router_json('{"intent": ') is None


def test_parse_unknown_intent_returns_none() -> None:
    assert parse_router_json('{"intent": "smalltalk"}') is None


async def test_classify_without_provider_returns_none() -> None:
    # conftest isolates env -> no provider keys -> no registry -> None.
    assert await classify("anything ambiguous") is None


async def test_classify_with_fake_model(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeModel:
        async def complete(self, *, system: str, prompt: str, max_tokens: int) -> str:
            return '{"intent": "schedule", "scope": "full"}'

    class FakeRegistry:
        def for_role(self, role: object) -> FakeModel:
            return FakeModel()

    monkeypatch.setattr(router_node, "try_get_model_registry", lambda: FakeRegistry())
    intent = await classify("show me everything")
    assert intent is not None
    assert intent.name is IntentName.SCHEDULE
    assert intent.scope is Scope.FULL
