"""Unit tests for SummaryService (slide path, deep path, caching, edge cases)."""

from __future__ import annotations

import pytest
from app.services import summaries
from app.services.lesson_map_store import YamlLessonMapStore
from app.services.summaries import SummaryService, SummaryStatus

from tests.fixtures.drive_fixtures import FakeDriveService


class FakeChatModel:
    def __init__(self) -> None:
        self.calls = 0

    async def complete(self, *, system: str, prompt: str, max_tokens: int) -> str:
        self.calls += 1
        return "SUMMARY TEXT"


class FakeRegistry:
    def __init__(self) -> None:
        self.model = FakeChatModel()

    def for_role(self, role: object) -> FakeChatModel:
        return self.model


class FakeTranscription:
    def __init__(self) -> None:
        self.calls = 0

    async def transcribe(self, *, drive_file_id: str, modified_time: str) -> str:
        self.calls += 1
        return "TRANSCRIPT TEXT"


def _lesson_map():  # type: ignore[no-untyped-def]
    return YamlLessonMapStore().load()


@pytest.fixture
def _patch_extract(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_extract(drive: object, file: dict[str, object]) -> str:
        return f"text of {file.get('name')}"

    monkeypatch.setattr(summaries, "extract_text", fake_extract)


async def test_slide_summary_ok(_patch_extract: None) -> None:
    registry = FakeRegistry()
    service = SummaryService(FakeDriveService(), _lesson_map(), registry)
    outcome = await service.summarize_lesson("12", deep=False, language="en")
    assert outcome.status is SummaryStatus.OK
    assert "Lesson 12" in outcome.lesson_key
    assert outcome.text == "SUMMARY TEXT"
    assert registry.model.calls == 1


async def test_summary_is_cached(_patch_extract: None) -> None:
    registry = FakeRegistry()
    service = SummaryService(FakeDriveService(), _lesson_map(), registry)
    await service.summarize_lesson("12", deep=False, language="en")
    await service.summarize_lesson("12", deep=False, language="en")
    assert registry.model.calls == 1  # second call served from cache


async def test_no_materials() -> None:
    registry = FakeRegistry()
    service = SummaryService(FakeDriveService({}), _lesson_map(), registry)
    outcome = await service.summarize_lesson("99", deep=False, language="en")
    assert outcome.status is SummaryStatus.NO_MATERIALS


async def test_llm_unavailable() -> None:
    service = SummaryService(FakeDriveService(), _lesson_map(), None)
    outcome = await service.summarize_lesson("12", deep=False, language="en")
    assert outcome.status is SummaryStatus.LLM_UNAVAILABLE


async def test_deep_uses_transcript() -> None:
    registry = FakeRegistry()
    transcription = FakeTranscription()
    service = SummaryService(
        FakeDriveService(), _lesson_map(), registry, transcription=transcription
    )
    outcome = await service.summarize_lesson("2", deep=True, language="en")
    assert outcome.status is SummaryStatus.OK
    assert transcription.calls >= 1  # Lesson 2 recording has parts
    assert registry.model.calls == 1
