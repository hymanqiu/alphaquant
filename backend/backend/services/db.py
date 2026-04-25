"""SQLAlchemy async engine + session factory.

This module owns the process-wide async ``engine`` and ``async_sessionmaker``.
Anything that needs a DB session imports ``get_session()`` (FastAPI dep) or
calls ``session_scope()`` (context manager) from non-request code.

The DB is **optional** at import time — when ``AQ_DATABASE_URL`` is empty the
module is in "no-DB" mode: ``is_db_configured()`` returns False and
auth-protected routes degrade to 503. This keeps the rest of the app
runnable in dev without Postgres.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from backend.config import settings

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """SQLAlchemy declarative base for all auth/user tables."""


_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def is_db_configured() -> bool:
    return bool(settings.database_url)


def get_engine() -> AsyncEngine:
    """Lazily build the async engine. Raises if AQ_DATABASE_URL is empty."""
    global _engine
    if _engine is None:
        if not settings.database_url:
            raise RuntimeError(
                "Database not configured: set AQ_DATABASE_URL "
                "(e.g. postgresql+asyncpg://user:pass@host:5432/db)"
            )
        _engine = create_async_engine(
            settings.database_url,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=5,
            future=True,
        )
        logger.info("DB engine initialized for %s", _engine.url.render_as_string(hide_password=True))
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=get_engine(),
            expire_on_commit=False,
            class_=AsyncSession,
        )
    return _session_factory


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    """Async context manager yielding a session with automatic commit/rollback."""
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency that yields a session per request."""
    factory = get_session_factory()
    async with factory() as session:
        yield session


async def close_engine() -> None:
    """Tear down the engine. Call from FastAPI lifespan shutdown."""
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
    _session_factory = None
