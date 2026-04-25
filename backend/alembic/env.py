"""Alembic environment for AlphaQuant.

Reads the DSN from ``backend.config.settings.database_url`` (loaded from the
project's ``.env`` file via Pydantic settings) so a single source of truth
governs connection details.

Supports async SQLAlchemy by running migrations through ``run_sync`` inside
an async connection. ``offline`` mode (``alembic upgrade head --sql``) is
also supported for SQL-script generation.
"""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from backend.config import settings
from backend.services.db import Base

# Importing the models here registers them with Base.metadata so autogenerate
# can detect schema diffs.
from backend.services.auth.models import IdentityProvider, User  # noqa: F401

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _resolved_url() -> str:
    """Prefer the runtime DSN; fall back to alembic.ini's placeholder."""
    return settings.database_url or config.get_main_option("sqlalchemy.url") or ""


def run_migrations_offline() -> None:
    """Generate SQL without a live connection."""
    url = _resolved_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def _do_run_migrations(connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online_async() -> None:
    """Run migrations in 'online' mode using an async engine."""
    url = _resolved_url()
    if not url:
        raise RuntimeError(
            "AQ_DATABASE_URL is empty — set it before running migrations."
        )

    connectable = async_engine_from_config(
        {"sqlalchemy.url": url},
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(_do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_migrations_online_async())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
