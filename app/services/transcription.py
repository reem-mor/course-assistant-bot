"""Transcription pipeline (worker-side).

Pipeline: download mp4 -> ffmpeg extract mono 16 kHz audio -> (chunk if long) -> ASR
(``gpt-4o-mini-transcribe``) -> stitch -> cache by ``drive_file_id + modifiedTime``.

This runs in the worker path, never inline in a chat handler (the chat side shows a
"working on it" note and the deep summary is produced out-of-band). ffmpeg + ASR are
mocked in tests - no real subprocess or network calls in the suite.
"""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from app.core.logging import get_logger
from app.services.drive import DriveService

_log = get_logger("transcription")


@runtime_checkable
class TranscriptionService(Protocol):
    """Produces cached transcripts for recording files."""

    async def transcribe(self, *, drive_file_id: str, modified_time: str) -> str: ...


class WhisperTranscriptionService:
    """ASR-backed transcription with content-keyed caching."""

    def __init__(
        self,
        drive: DriveService,
        *,
        api_key: str,
        asr_model: str = "gpt-4o-mini-transcribe",
        cache: dict[str, str] | None = None,
    ) -> None:
        self._drive = drive
        self._api_key = api_key
        self._asr_model = asr_model
        self._cache: dict[str, str] = cache if cache is not None else {}

    @staticmethod
    def _key(drive_file_id: str, modified_time: str) -> str:
        return f"{drive_file_id}:{modified_time}"

    async def _extract_audio(self, drive_file_id: str, workdir: Path) -> Path:
        """Download the video and extract mono 16 kHz wav via ffmpeg."""
        data = await self._drive.download_file(drive_file_id)
        src = workdir / "video.mp4"
        dst = workdir / "audio.wav"
        src.write_bytes(data)
        proc = await asyncio.create_subprocess_exec(
            "ffmpeg", "-y", "-i", str(src), "-ac", "1", "-ar", "16000", str(dst),
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(f"ffmpeg failed: {stderr.decode('utf-8', 'replace')[:500]}")
        return dst

    def _chunk(self, audio_path: Path) -> list[Path]:
        """Split long audio into chunks. v1 keeps a single chunk (chunking TBD Phase 7)."""
        return [audio_path]

    async def _transcribe_chunk(self, audio_path: Path) -> str:
        """Transcribe one audio chunk via the ASR model."""
        import openai

        client: Any = openai.AsyncOpenAI(api_key=self._api_key)
        with audio_path.open("rb") as fh:
            resp = await client.audio.transcriptions.create(
                model=self._asr_model, file=fh
            )
        return str(getattr(resp, "text", "") or "")

    async def transcribe(self, *, drive_file_id: str, modified_time: str) -> str:
        """Return the transcript for a recording, using cache when available."""
        key = self._key(drive_file_id, modified_time)
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        with tempfile.TemporaryDirectory() as tmp:
            workdir = Path(tmp)
            audio = await self._extract_audio(drive_file_id, workdir)
            parts = [await self._transcribe_chunk(chunk) for chunk in self._chunk(audio)]
        transcript = "\n".join(p for p in parts if p).strip()
        self._cache[key] = transcript
        _log.info("transcribed", drive_file_id=drive_file_id, chars=len(transcript))
        return transcript
