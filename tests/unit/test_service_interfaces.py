"""Smoke tests that every service interface imports and is a usable Protocol.

Guards the stable import paths that later phases depend on.
"""

from __future__ import annotations

from app.services.drive import DriveService, DriveUploader
from app.services.email import EmailAttachment, EmailService
from app.services.llm import ChatModel, ModelRegistry, ModelRole
from app.services.notifier import BroadcastResult, Notifier
from app.services.recommendations import Recommendation, RecommendationService
from app.services.schedule import ScheduleService
from app.services.transcription import TranscriptionService
from app.services.vectorstore import RetrievedChunk, VectorStore


def test_protocols_importable() -> None:
    protocols = [
        DriveService,
        DriveUploader,
        EmailService,
        ChatModel,
        ModelRegistry,
        ScheduleService,
        TranscriptionService,
        VectorStore,
        Notifier,
        RecommendationService,
    ]
    assert all(p is not None for p in protocols)


def test_model_roles_present() -> None:
    assert ModelRole.ROUTER == "router"
    assert ModelRole.SUMMARIZER == "summarizer"
    assert ModelRole.EMBEDDINGS == "embeddings"


def test_dataclasses_construct() -> None:
    att = EmailAttachment(filename="hw.docx", content=b"x", mime_type="application/octet-stream")
    assert att.filename == "hw.docx"

    chunk = RetrievedChunk(text="t", score=0.9, drive_file_id="id", view_url="http://x")
    assert chunk.score == 0.9

    result = BroadcastResult(sent=5, failed=1)
    assert result.sent == 5

    rec = Recommendation(title="Docs", url="http://x", source="external")
    assert rec.source == "external"
