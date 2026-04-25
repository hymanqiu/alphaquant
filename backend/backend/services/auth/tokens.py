"""JWT session tokens (HS256).

Tokens are short and audited:

- Signed with ``AQ_JWT_SECRET``; rotation = bump the secret (invalidates all
  outstanding tokens, which is fine for an MVP).
- Carry only the user id, tier, and email — no PII beyond email.
- Default TTL is 7 days. We don't implement refresh tokens for the MVP; the
  client just re-authenticates when its token expires.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from jose import JWTError, jwt

from backend.config import settings

logger = logging.getLogger(__name__)

_ALGORITHM = "HS256"


class SessionTokenError(Exception):
    """Token is malformed, expired, or signed with a different secret."""


@dataclass(frozen=True)
class SessionClaims:
    """Decoded JWT payload."""

    user_id: int
    email: str
    tier: str
    issued_at: int
    expires_at: int


def issue_session_token(*, user_id: int, email: str, tier: str) -> str:
    """Mint a fresh JWT for an authenticated user."""
    if not settings.jwt_secret:
        raise SessionTokenError("AQ_JWT_SECRET is not configured")

    now = int(time.time())
    payload = {
        "iss": settings.jwt_issuer,
        "sub": str(user_id),
        "email": email,
        "tier": tier,
        "iat": now,
        "exp": now + settings.jwt_access_ttl_seconds,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=_ALGORITHM)


def decode_session_token(token: str) -> SessionClaims:
    """Verify and decode a JWT. Raises ``SessionTokenError`` on any failure."""
    if not settings.jwt_secret:
        raise SessionTokenError("AQ_JWT_SECRET is not configured")
    try:
        payload = jwt.decode(
            token, settings.jwt_secret, algorithms=[_ALGORITHM],
            options={"require": ["exp", "sub", "email"]},
        )
    except JWTError as e:
        raise SessionTokenError(str(e)) from e

    try:
        user_id = int(payload["sub"])
    except (KeyError, ValueError, TypeError) as e:
        raise SessionTokenError("missing/invalid sub claim") from e

    return SessionClaims(
        user_id=user_id,
        email=str(payload.get("email", "")),
        tier=str(payload.get("tier", "free")),
        issued_at=int(payload.get("iat", 0)),
        expires_at=int(payload["exp"]),
    )
