"""Watchlist CRUD.

For Phase 3 we ship persistence + manual re-analysis (the user clicks
"Re-check" in the sidebar). The cron task that auto-runs analyses + emails
when MoS crosses ``target_mos_pct`` is deferred to a follow-up — the schema
already supports it via ``last_checked_at`` / ``last_mos_pct`` /
``last_signal``.

Endpoints:

- ``GET    /api/watchlist``            — list mine
- ``PUT    /api/watchlist/{ticker}``   — upsert (idempotent on ticker)
- ``DELETE /api/watchlist/{ticker}``   — remove mine
"""

from __future__ import annotations

import logging
import re
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.auth import User, get_current_user
from backend.services.db import get_session, is_db_configured
from backend.services.watchlist import (
    WatchlistItem,
    delete_owned,
    list_for_user,
    upsert,
)

logger = logging.getLogger(__name__)

router = APIRouter()

_TICKER_RE = re.compile(r"^[A-Za-z]{1,8}$")


def _require_db() -> None:
    if not is_db_configured():
        raise HTTPException(
            status_code=503,
            detail="Watchlist disabled: AQ_DATABASE_URL is not configured.",
        )


def _payload(item: WatchlistItem) -> dict[str, Any]:
    return {
        "id": item.id,
        "ticker": item.ticker,
        "target_mos_pct": item.target_mos_pct,
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "updated_at": item.updated_at.isoformat() if item.updated_at else None,
        "last_checked_at": (
            item.last_checked_at.isoformat() if item.last_checked_at else None
        ),
        "last_mos_pct": item.last_mos_pct,
        "last_signal": item.last_signal,
    }


class WatchlistUpsertRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    target_mos_pct: float | None = Field(default=None, ge=-100, le=100)


@router.get("/api/watchlist")
async def list_mine(
    user: Annotated[User, Depends(get_current_user)],
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    _require_db()
    items = await list_for_user(session, user_id=user.id)
    return {"items": [_payload(i) for i in items]}


@router.put("/api/watchlist/{ticker}")
async def put_ticker(
    ticker: str,
    body: WatchlistUpsertRequest,
    user: Annotated[User, Depends(get_current_user)],
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    _require_db()
    if not _TICKER_RE.match(ticker):
        raise HTTPException(
            status_code=400,
            detail="Invalid ticker. Must be 1-8 alphabetic characters.",
        )
    item = await upsert(
        session,
        user_id=user.id,
        ticker=ticker,
        target_mos_pct=body.target_mos_pct,
    )
    await session.commit()
    return _payload(item)


@router.delete("/api/watchlist/{ticker}", status_code=204)
async def delete_ticker(
    ticker: str,
    user: Annotated[User, Depends(get_current_user)],
    session: AsyncSession = Depends(get_session),
) -> None:
    _require_db()
    if not _TICKER_RE.match(ticker):
        raise HTTPException(status_code=400, detail="Invalid ticker.")

    # Look up by ticker (not id) since the URL is ticker-keyed.
    items = await list_for_user(session, user_id=user.id)
    target = next((i for i in items if i.ticker.upper() == ticker.upper()), None)
    if target is None:
        raise HTTPException(status_code=404, detail="Not on your watchlist")

    await delete_owned(session, item_id=target.id, user_id=user.id)
    await session.commit()
