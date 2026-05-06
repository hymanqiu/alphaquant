"""Saved thesis CRUD + public share endpoint.

Endpoints:

- ``POST   /api/saved-thesis``         — create (auth required)
- ``GET    /api/saved-thesis``         — list mine (auth required)
- ``GET    /api/saved-thesis/{id}``    — read mine (auth required)
- ``DELETE /api/saved-thesis/{id}``    — delete mine (auth required)
- ``GET    /api/share/thesis/{id}``    — read a public thesis (no auth) —
                                         only returns when ``is_public=True``.

The user's intent: snapshot a thesis today, see how the numbers have moved
on revisit, share a public link with peers. The diff vs. live re-analysis
happens client-side; the backend stores the snapshot verbatim.
"""

from __future__ import annotations

import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.auth import User, get_current_user
from backend.services.db import get_session, is_db_configured
from backend.services.saved_thesis import (
    SavedThesis,
    create_thesis,
    delete_owned,
    get_owned,
    get_public,
    list_for_user,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def _require_db() -> None:
    if not is_db_configured():
        raise HTTPException(
            status_code=503,
            detail="Saved theses disabled: AQ_DATABASE_URL is not configured.",
        )


# ---------------------------------------------------------------------------
# Request / response shapes
# ---------------------------------------------------------------------------


# Hard bounds on snapshot size. The save flow is authenticated, but a
# saved thesis can be re-served via the unauthenticated public share
# endpoint, so we constrain payload size both as a storage DoS guard and
# as an abuse-amplification guard. Real analyses currently emit ~12-18
# components; ~20 hero fields. The limits here are well above realistic
# cases but small enough that an attacker can't park MBs of JSON in the
# table.
_MAX_COMPONENT_INSTRUCTIONS = 30
_MAX_HERO_KEYS = 20
_MAX_COMPONENT_TYPE_LEN = 64
_MAX_COMPONENT_ID_LEN = 64


class _ComponentInstruction(BaseModel):
    """Mirror of the frontend ComponentInstruction shape."""

    model_config = ConfigDict(extra="allow")
    component_type: str = Field(max_length=_MAX_COMPONENT_TYPE_LEN)
    props: dict[str, Any]
    id: str = Field(max_length=_MAX_COMPONENT_ID_LEN)


class SavedThesisCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ticker: str = Field(min_length=1, max_length=8)
    title: str | None = Field(default=None, max_length=200)
    is_public: bool = True
    hero_snapshot: dict[str, Any]
    components_snapshot: list[_ComponentInstruction] = Field(
        max_length=_MAX_COMPONENT_INSTRUCTIONS,
    )

    @field_validator("hero_snapshot")
    @classmethod
    def _check_hero_size(cls, v: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(v, dict):
            raise ValueError("hero_snapshot must be an object")
        if len(v) > _MAX_HERO_KEYS:
            raise ValueError(
                f"hero_snapshot too large (max {_MAX_HERO_KEYS} keys, got {len(v)})"
            )
        return v


def _public_payload(thesis: SavedThesis) -> dict[str, Any]:
    return {
        "id": thesis.id,
        "ticker": thesis.ticker,
        "title": thesis.title,
        "is_public": thesis.is_public,
        "created_at": thesis.created_at.isoformat() if thesis.created_at else None,
        "hero_snapshot": thesis.hero_snapshot,
        "components_snapshot": thesis.components_snapshot,
    }


def _summary_payload(thesis: SavedThesis) -> dict[str, Any]:
    """Trimmed payload for sidebar list (no full components dump)."""
    return {
        "id": thesis.id,
        "ticker": thesis.ticker,
        "title": thesis.title,
        "is_public": thesis.is_public,
        "created_at": thesis.created_at.isoformat() if thesis.created_at else None,
        "hero_snapshot": thesis.hero_snapshot,
    }


# ---------------------------------------------------------------------------
# Authenticated CRUD
# ---------------------------------------------------------------------------


@router.post("/api/saved-thesis", status_code=201)
async def create(
    body: SavedThesisCreateRequest,
    user: Annotated[User, Depends(get_current_user)],
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    _require_db()
    thesis = await create_thesis(
        session,
        user_id=user.id,
        ticker=body.ticker,
        title=body.title,
        is_public=body.is_public,
        hero_snapshot=body.hero_snapshot,
        components_snapshot=[c.model_dump() for c in body.components_snapshot],
    )
    await session.commit()
    return _public_payload(thesis)


@router.get("/api/saved-thesis")
async def list_mine(
    user: Annotated[User, Depends(get_current_user)],
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    _require_db()
    items = await list_for_user(session, user_id=user.id)
    return {"items": [_summary_payload(t) for t in items]}


@router.get("/api/saved-thesis/{thesis_id}")
async def read_mine(
    thesis_id: str,
    user: Annotated[User, Depends(get_current_user)],
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    _require_db()
    thesis = await get_owned(session, thesis_id=thesis_id, user_id=user.id)
    if thesis is None:
        raise HTTPException(status_code=404, detail="Not found")
    return _public_payload(thesis)


@router.delete("/api/saved-thesis/{thesis_id}", status_code=204)
async def delete(
    thesis_id: str,
    user: Annotated[User, Depends(get_current_user)],
    session: AsyncSession = Depends(get_session),
) -> None:
    _require_db()
    deleted = await delete_owned(session, thesis_id=thesis_id, user_id=user.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Not found")
    await session.commit()


# ---------------------------------------------------------------------------
# Public share — no auth required, only returns when is_public=True
# ---------------------------------------------------------------------------


@router.get("/api/share/thesis/{thesis_id}")
async def read_public(
    thesis_id: str,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    _require_db()
    thesis = await get_public(session, thesis_id=thesis_id)
    if thesis is None:
        raise HTTPException(status_code=404, detail="Not found or not public")
    return _public_payload(thesis)
