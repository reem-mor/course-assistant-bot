"""Unit tests for the transcription pipeline (ffmpeg + ASR mocked)."""

from __future__ import annotations

from pathlib import Path

import pytest
from app.services.transcription import WhisperTranscriptionService

from tests.fixtures.drive_fixtures import FakeDriveService


def _service() -> WhisperTranscriptionService:
    return WhisperTranscriptionService(FakeDriveService(), api_key="x")


async def test_transcribe_and_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    svc = _service()
    chunk_calls = {"n": 0}

    async def fake_extract(drive_file_id: str, workdir: Path) -> Path:
        return workdir / "audio.wav"

    async def fake_chunk_transcribe(audio_path: Path) -> str:
        chunk_calls["n"] += 1
        return "HELLO WORLD"

    monkeypatch.setattr(svc, "_extract_audio", fake_extract)
    monkeypatch.setattr(svc, "_transcribe_chunk", fake_chunk_transcribe)

    first = await svc.transcribe(drive_file_id="vid1", modified_time="t1")
    second = await svc.transcribe(drive_file_id="vid1", modified_time="t1")

    assert first == "HELLO WORLD"
    assert second == "HELLO WORLD"
    assert chunk_calls["n"] == 1  # second call served from cache


async def test_different_modified_time_retranscribes(monkeypatch: pytest.MonkeyPatch) -> None:
    svc = _service()
    calls = {"n": 0}

    async def fake_extract(drive_file_id: str, workdir: Path) -> Path:
        return workdir / "audio.wav"

    async def fake_chunk_transcribe(audio_path: Path) -> str:
        calls["n"] += 1
        return "X"

    monkeypatch.setattr(svc, "_extract_audio", fake_extract)
    monkeypatch.setattr(svc, "_transcribe_chunk", fake_chunk_transcribe)

    await svc.transcribe(drive_file_id="vid1", modified_time="t1")
    await svc.transcribe(drive_file_id="vid1", modified_time="t2")
    assert calls["n"] == 2  # modifiedTime changed -> cache miss
