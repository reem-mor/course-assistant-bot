"""SQLAlchemy ORM models (Phase 5 datastore).

Tables: subscribers, drive_state, broadcast_log, audit_log. Other tables
(materials_index, submission_drafts) land in their own phases.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.repo.db import Base


def _utcnow() -> datetime:
    return datetime.now(tz=UTC)


class Subscriber(Base):
    """A Telegram user registered via /start."""

    __tablename__ = "subscribers"

    telegram_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    language: Mapped[str] = mapped_column(String(2), default="he")
    subscribed: Mapped[bool] = mapped_column(Boolean, default=True)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class DriveState(Base):
    """Tracks each Drive file's last-seen modifiedTime for the watcher diff."""

    __tablename__ = "drive_state"

    file_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    parent: Mapped[str | None] = mapped_column(String(128), nullable=True)
    modified_time: Mapped[str | None] = mapped_column(String(64), nullable=True)
    kind: Mapped[str | None] = mapped_column(String(32), nullable=True)
    lesson_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )


class BroadcastLog(Base):
    """Idempotency ledger: one row per broadcast key, ensuring no double-send."""

    __tablename__ = "broadcast_log"

    idempotency_key: Mapped[str] = mapped_column(String(128), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    sent: Mapped[int] = mapped_column(Integer, default=0)
    failed: Mapped[int] = mapped_column(Integer, default=0)


class AuditLog(Base):
    """Append-only audit trail for admin actions."""

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    action: Mapped[str] = mapped_column(String(64))
    actor_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class Admin(Base):
    """A dynamically-added admin (layered over the env allowlist)."""

    __tablename__ = "admins"

    telegram_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    added_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class MaterialChunk(Base):
    """An embedded chunk of course material for RAG retrieval (feature 6.3).

    The embedding is stored as a JSON array so the same schema works on SQLite and
    Postgres; pgvector-accelerated search is a Phase 7 optimization behind the same
    VectorStore interface.
    """

    __tablename__ = "materials_index"

    chunk_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    drive_file_id: Mapped[str] = mapped_column(String(128))
    lesson_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    name: Mapped[str] = mapped_column(String(512))
    view_url: Mapped[str] = mapped_column(String(512))
    text: Mapped[str] = mapped_column(Text)
    embedding: Mapped[str] = mapped_column(Text)  # JSON-encoded list[float]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
