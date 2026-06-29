"""Tests for the Phase 5 repositories against an in-memory SQLite datastore."""

from __future__ import annotations

from typing import Any

from app.repo.repositories import (
    BroadcastLogRepo,
    DriveStateRepo,
    SubscriberRepo,
)


async def test_subscriber_lifecycle(db_sessionmaker: Any) -> None:
    repo = SubscriberRepo(db_sessionmaker)
    await repo.upsert(1, language="en")
    await repo.upsert(2, language="he")
    assert set(await repo.active_ids()) == {1, 2}

    await repo.unsubscribe(1)
    assert set(await repo.active_ids()) == {2}

    # Re-subscribing flips it back on.
    await repo.upsert(1, language="he")
    assert set(await repo.active_ids()) == {1, 2}


async def test_subscriber_set_language(db_sessionmaker: Any) -> None:
    repo = SubscriberRepo(db_sessionmaker)
    await repo.upsert(5, language="he")
    await repo.set_language(5, "en")
    sub = await repo.get(5)
    assert sub is not None and sub.language == "en"


async def test_drive_state_upsert_and_known(db_sessionmaker: Any) -> None:
    repo = DriveStateRepo(db_sessionmaker)
    assert await repo.is_empty()
    await repo.upsert(file_id="f1", parent="p", modified_time="t1", kind="slides", lesson_key=None)
    assert not await repo.is_empty()
    known = await repo.known_modified()
    assert known == {"f1": "t1"}

    await repo.upsert(file_id="f1", parent="p", modified_time="t2", kind="slides", lesson_key=None)
    assert (await repo.known_modified())["f1"] == "t2"


async def test_broadcast_log_idempotency(db_sessionmaker: Any) -> None:
    repo = BroadcastLogRepo(db_sessionmaker)
    assert not await repo.seen("k1")
    await repo.record("k1", sent=3, failed=0)
    assert await repo.seen("k1")
    # Recording the same key again is a no-op (no error).
    await repo.record("k1", sent=9, failed=9)
