"""Repositories over the Phase 5 datastore.

Each repo takes an ``async_sessionmaker`` and opens a short-lived session per call, so
callers (handlers, worker jobs) don't manage session lifecycles.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.repo.models import Admin, AuditLog, BroadcastLog, DriveState, Subscriber

Sessionmaker = async_sessionmaker[AsyncSession]


class SubscriberRepo:
    """CRUD for course subscribers."""

    def __init__(self, sessionmaker: Sessionmaker) -> None:
        self._sm = sessionmaker

    async def upsert(
        self, telegram_id: int, *, language: str = "he", full_name: str | None = None
    ) -> None:
        """Register or re-activate a subscriber."""
        async with self._sm() as session, session.begin():
            existing = await session.get(Subscriber, telegram_id)
            if existing is None:
                session.add(
                    Subscriber(
                        telegram_id=telegram_id,
                        language=language,
                        subscribed=True,
                        full_name=full_name,
                    )
                )
            else:
                existing.subscribed = True
                existing.language = language
                if full_name:
                    existing.full_name = full_name

    async def set_language(self, telegram_id: int, language: str) -> None:
        async with self._sm() as session, session.begin():
            sub = await session.get(Subscriber, telegram_id)
            if sub is not None:
                sub.language = language

    async def unsubscribe(self, telegram_id: int) -> None:
        async with self._sm() as session, session.begin():
            sub = await session.get(Subscriber, telegram_id)
            if sub is not None:
                sub.subscribed = False

    async def active_ids(self) -> list[int]:
        """Return the telegram ids of all currently subscribed users."""
        async with self._sm() as session:
            result = await session.execute(
                select(Subscriber.telegram_id).where(Subscriber.subscribed.is_(True))
            )
            return [row[0] for row in result.all()]

    async def get(self, telegram_id: int) -> Subscriber | None:
        async with self._sm() as session:
            sub: Subscriber | None = await session.get(Subscriber, telegram_id)
            return sub


class DriveStateRepo:
    """Tracks Drive files seen by the watcher."""

    def __init__(self, sessionmaker: Sessionmaker) -> None:
        self._sm = sessionmaker

    async def is_empty(self) -> bool:
        """True if no Drive state has been recorded yet (first-run detection)."""
        async with self._sm() as session:
            result = await session.execute(select(DriveState.file_id).limit(1))
            return result.first() is None

    async def get(self, file_id: str) -> DriveState | None:
        async with self._sm() as session:
            state: DriveState | None = await session.get(DriveState, file_id)
            return state

    async def upsert(
        self,
        *,
        file_id: str,
        parent: str | None,
        modified_time: str | None,
        kind: str | None,
        lesson_key: str | None,
    ) -> None:
        async with self._sm() as session, session.begin():
            existing = await session.get(DriveState, file_id)
            if existing is None:
                session.add(
                    DriveState(
                        file_id=file_id,
                        parent=parent,
                        modified_time=modified_time,
                        kind=kind,
                        lesson_key=lesson_key,
                    )
                )
            else:
                existing.parent = parent
                existing.modified_time = modified_time
                existing.kind = kind
                existing.lesson_key = lesson_key

    async def known_modified(self) -> dict[str, str | None]:
        """Return a map of file_id -> last-seen modifiedTime."""
        async with self._sm() as session:
            result = await session.execute(
                select(DriveState.file_id, DriveState.modified_time)
            )
            return {row[0]: row[1] for row in result.all()}


class BroadcastLogRepo:
    """Idempotency ledger for broadcasts."""

    def __init__(self, sessionmaker: Sessionmaker) -> None:
        self._sm = sessionmaker

    async def seen(self, idempotency_key: str) -> bool:
        async with self._sm() as session:
            return await session.get(BroadcastLog, idempotency_key) is not None

    async def record(self, idempotency_key: str, *, sent: int, failed: int) -> None:
        async with self._sm() as session, session.begin():
            if await session.get(BroadcastLog, idempotency_key) is None:
                session.add(
                    BroadcastLog(idempotency_key=idempotency_key, sent=sent, failed=failed)
                )


class AdminRepo:
    """Dynamically-managed admins, layered over the env allowlist."""

    def __init__(self, sessionmaker: Sessionmaker) -> None:
        self._sm = sessionmaker

    async def add(self, telegram_id: int, *, added_by: int | None) -> None:
        async with self._sm() as session, session.begin():
            if await session.get(Admin, telegram_id) is None:
                session.add(Admin(telegram_id=telegram_id, added_by=added_by))

    async def remove(self, telegram_id: int) -> None:
        async with self._sm() as session, session.begin():
            existing = await session.get(Admin, telegram_id)
            if existing is not None:
                await session.delete(existing)

    async def list_ids(self) -> list[int]:
        async with self._sm() as session:
            result = await session.execute(select(Admin.telegram_id))
            return [row[0] for row in result.all()]

    async def contains(self, telegram_id: int) -> bool:
        async with self._sm() as session:
            return await session.get(Admin, telegram_id) is not None


class AuditLogRepo:
    """Append-only audit trail."""

    def __init__(self, sessionmaker: Sessionmaker) -> None:
        self._sm = sessionmaker

    async def add(self, *, action: str, actor_id: int | None, detail: str | None) -> None:
        async with self._sm() as session, session.begin():
            session.add(AuditLog(action=action, actor_id=actor_id, detail=detail))
