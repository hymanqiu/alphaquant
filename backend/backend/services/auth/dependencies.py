"""FastAPI dependencies for auth.

Two patterns:

- ``get_current_user`` — required auth; 401 if missing/invalid.
- ``get_optional_user`` — best-effort; returns ``None`` if missing/invalid.
  Used by routes that want to vary behavior by tier (e.g. /analyze gates
  Pro nodes by user.tier when present, falls back to "free" otherwise).

Tokens are read from ``Authorization: Bearer ...`` header OR from a session
cookie (``aq_session``). Cookie is preferred for browser flows; bearer for
API clients.
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import Cookie, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.db import get_session

from .models import User
from .service import AuthService
from .tokens import SessionTokenError, decode_session_token

logger = logging.getLogger(__name__)

SESSION_COOKIE = "aq_session"


def _extract_token(
    authorization: str | None, cookie: str | None,
) -> str | None:
    """Return the bearer token from headers/cookies, or None."""
    if cookie:
        return cookie
    if authorization and authorization.lower().startswith("bearer "):
        return authorization.split(" ", 1)[1].strip()
    return None


async def get_optional_user(
    authorization: Annotated[str | None, Header()] = None,
    aq_session: Annotated[str | None, Cookie()] = None,
    session: AsyncSession = Depends(get_session),
) -> User | None:
    """Return the authenticated user if a valid session is present; else None."""
    token = _extract_token(authorization, aq_session)
    if not token:
        return None
    try:
        claims = decode_session_token(token)
    except SessionTokenError:
        return None

    auth = AuthService(session)
    user = await auth.get_by_id(claims.user_id)
    if user is None or not user.is_active:
        return None
    return user


async def get_current_user(
    user: User | None = Depends(get_optional_user),
) -> User:
    """Return the authenticated user; raise 401 if absent."""
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


async def require_pro(
    user: User = Depends(get_current_user),
) -> User:
    """Gate a route to Pro-tier users. 403 for free-tier."""
    if user.tier != "pro":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "pro_required",
                "message": "This feature requires a Pro subscription.",
            },
        )
    return user


async def require_admin_tier(
    user: User = Depends(get_current_user),
) -> User:
    """Gate a route to admin-tier users (currently piggybacks on tier=admin)."""
    if user.tier != "admin":
        raise HTTPException(status_code=403, detail="Admin role required")
    return user
