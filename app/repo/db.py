"""Async database engine, session factory, and schema bootstrap.

SQLAlchemy 2.x async. ``SUPABASE_DB_URL`` (Postgres/asyncpg) is preferred for production;
otherwise ``DATABASE_URL`` (sqlite+aiosqlite) is used for local dev. Phase 5 uses
``create_all`` for schema; Alembic migrations are deferred to Phase 7.
"""

from __future__ import annotations

from functools import lru_cache

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.logging import get_logger
from app.core.settings import Settings, get_settings

_log = get_logger("repo.db")


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


def _resolve_url(settings: Settings) -> str:
    """Prefer the Supabase Postgres URL (if non-empty), else the dev database URL."""
    if settings.supabase_db_url is not None:
        supabase = settings.supabase_db_url.get_secret_value().strip()
        # Guard against blank/garbage values (e.g. a stray dotenv inline comment).
        if "://" in supabase:
            return supabase
    return settings.database_url


@lru_cache(maxsize=1)
def get_engine() -> AsyncEngine:
    """Return a cached async engine built from settings."""
    url = _resolve_url(get_settings())
    return create_async_engine(url, future=True, pool_pre_ping=True)


@lru_cache(maxsize=1)
def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    """Return a cached async session factory."""
    return async_sessionmaker(get_engine(), expire_on_commit=False)


async def init_db() -> None:
    """Create all tables if they do not exist (v1 schema bootstrap)."""
    # Import models so they register on Base.metadata before create_all.
    from app.repo import models  # noqa: F401

    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    _log.info("db_initialized")


def reset_engine() -> None:
    """Clear cached engine/sessionmaker (used by tests to swap databases)."""
    get_engine.cache_clear()
    get_sessionmaker.cache_clear()
