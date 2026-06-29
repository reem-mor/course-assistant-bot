"""Alembic async migration environment.

Resolves the database URL from app settings (SUPABASE_DB_URL preferred, else
DATABASE_URL) and runs migrations against the async engine.
"""

from __future__ import annotations

import asyncio

from alembic import context
from app.core.settings import get_settings
from app.repo import models  # noqa: F401 - register models on the metadata
from app.repo.db import Base, _resolve_url
from sqlalchemy.ext.asyncio import create_async_engine

target_metadata = Base.metadata


def _url() -> str:
    return _resolve_url(get_settings())


def run_migrations_offline() -> None:
    context.configure(
        url=_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def _do_run_migrations(connection: object) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)  # type: ignore[arg-type]
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    engine = create_async_engine(_url(), future=True)
    async with engine.connect() as connection:
        await connection.run_sync(_do_run_migrations)
    await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
