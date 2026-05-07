"""SavedThesis ORM model + small CRUD helpers.

A SavedThesis is a snapshot a Pro user pins from the analysis canvas: hero
fields (signal, MoS, confidence, thesis line, prices) + the full
ComponentInstruction list, frozen at save time. On revisit the user can see
how those numbers have moved, and a public ``/s/<id>`` URL renders a
read-only view of the snapshot.

Design notes:

- ``id`` is a UUID v4 string so share URLs are non-enumerable.
- ``hero_snapshot`` is a small JSON blob with just the hero-strip fields —
  cheap to read for sidebar diffs without parsing the full components dump.
- ``components_snapshot`` is the entire ComponentInstruction list (potentially
  19 entries, ~10–50 KB JSON). Stored as JSONB on Postgres for indexing if
  ever needed.
- ``is_public`` defaults to True since the only reason a user saves+keeps a
  thesis is usually to share it. They can flip privacy later.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from backend.services.db import Base


def _new_id() -> str:
    return str(uuid.uuid4())


class SavedThesis(Base):
    __tablename__ = "saved_theses"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    ticker: Mapped[str] = mapped_column(String(8), nullable=False, index=True)
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    is_public: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true",
    )

    # Compact hero snapshot for cheap sidebar diff rendering.
    hero_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    # Full ComponentInstruction[] for the share/read-only canvas view.
    components_snapshot: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<SavedThesis id={self.id} user_id={self.user_id} "
            f"ticker={self.ticker}>"
        )


# ---------------------------------------------------------------------------
# CRUD helpers — kept tiny since route handlers stay thin.
# ---------------------------------------------------------------------------


async def create_thesis(
    session: AsyncSession,
    *,
    user_id: int,
    ticker: str,
    hero_snapshot: dict[str, Any],
    components_snapshot: list[dict[str, Any]],
    title: str | None = None,
    is_public: bool = True,
) -> SavedThesis:
    thesis = SavedThesis(
        user_id=user_id,
        ticker=ticker.upper(),
        title=title,
        is_public=is_public,
        hero_snapshot=hero_snapshot,
        components_snapshot=components_snapshot,
    )
    session.add(thesis)
    await session.flush()
    return thesis


async def list_for_user(
    session: AsyncSession, *, user_id: int,
) -> list[SavedThesis]:
    from sqlalchemy import select

    stmt = (
        select(SavedThesis)
        .where(SavedThesis.user_id == user_id)
        .order_by(SavedThesis.created_at.desc())
    )
    res = await session.execute(stmt)
    return list(res.scalars().all())


async def get_owned(
    session: AsyncSession, *, thesis_id: str, user_id: int,
) -> SavedThesis | None:
    from sqlalchemy import select

    stmt = select(SavedThesis).where(
        SavedThesis.id == thesis_id,
        SavedThesis.user_id == user_id,
    )
    res = await session.execute(stmt)
    return res.scalar_one_or_none()


async def get_public(
    session: AsyncSession, *, thesis_id: str,
) -> SavedThesis | None:
    """Look up a thesis by id only when it is publicly shared."""
    from sqlalchemy import select

    stmt = select(SavedThesis).where(
        SavedThesis.id == thesis_id,
        SavedThesis.is_public.is_(True),
    )
    res = await session.execute(stmt)
    return res.scalar_one_or_none()


async def delete_owned(
    session: AsyncSession, *, thesis_id: str, user_id: int,
) -> bool:
    thesis = await get_owned(session, thesis_id=thesis_id, user_id=user_id)
    if thesis is None:
        return False
    await session.delete(thesis)
    return True
