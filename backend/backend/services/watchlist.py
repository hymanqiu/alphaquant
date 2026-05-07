"""WatchlistItem ORM model + CRUD helpers.

Users add tickers to their watchlist with an optional MoS threshold. A future
cron task will re-run analysis daily and email when the threshold is crossed
— for now we only persist the items and expose a manual "checked" timestamp
that a future job can update.

Schema:
- ``user_id + ticker`` is unique; you can only watch each ticker once.
- ``target_mos_pct`` is the alert threshold ("notify when MoS >= X%"); null
  means "watch but no auto-alert".
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from backend.services.db import Base


class WatchlistItem(Base):
    __tablename__ = "watchlist_items"
    __table_args__ = (
        UniqueConstraint("user_id", "ticker", name="uq_watchlist_user_ticker"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    ticker: Mapped[str] = mapped_column(String(8), nullable=False, index=True)
    target_mos_pct: Mapped[float | None] = mapped_column(Float, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    last_checked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    last_mos_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_signal: Mapped[str | None] = mapped_column(String(32), nullable=True)

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<WatchlistItem id={self.id} user_id={self.user_id} "
            f"ticker={self.ticker}>"
        )


# ---------------------------------------------------------------------------
# CRUD helpers
# ---------------------------------------------------------------------------


async def list_for_user(
    session: AsyncSession, *, user_id: int,
) -> list[WatchlistItem]:
    from sqlalchemy import select

    stmt = (
        select(WatchlistItem)
        .where(WatchlistItem.user_id == user_id)
        .order_by(WatchlistItem.created_at.desc())
    )
    res = await session.execute(stmt)
    return list(res.scalars().all())


async def get_owned(
    session: AsyncSession, *, item_id: int, user_id: int,
) -> WatchlistItem | None:
    from sqlalchemy import select

    stmt = select(WatchlistItem).where(
        WatchlistItem.id == item_id,
        WatchlistItem.user_id == user_id,
    )
    res = await session.execute(stmt)
    return res.scalar_one_or_none()


async def upsert(
    session: AsyncSession,
    *,
    user_id: int,
    ticker: str,
    target_mos_pct: float | None,
) -> WatchlistItem:
    """Create or update — keyed on (user_id, ticker)."""
    from sqlalchemy import select

    ticker = ticker.upper()
    stmt = select(WatchlistItem).where(
        WatchlistItem.user_id == user_id,
        WatchlistItem.ticker == ticker,
    )
    existing = (await session.execute(stmt)).scalar_one_or_none()
    if existing is not None:
        existing.target_mos_pct = target_mos_pct
        await session.flush()
        return existing

    item = WatchlistItem(
        user_id=user_id, ticker=ticker, target_mos_pct=target_mos_pct,
    )
    session.add(item)
    await session.flush()
    return item


async def delete_owned(
    session: AsyncSession, *, item_id: int, user_id: int,
) -> bool:
    item = await get_owned(session, item_id=item_id, user_id=user_id)
    if item is None:
        return False
    await session.delete(item)
    return True
