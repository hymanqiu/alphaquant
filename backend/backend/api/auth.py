"""Auth API routes.

One router covering all three identity providers, plus a small ``/me`` and
``/logout`` for frontend session management. The bulk of the logic lives in
``services.auth`` — these handlers are thin glue.

All successful logins set an HTTP-only ``aq_session`` cookie carrying our
JWT; SPA clients can also read the token from the JSON response body and
attach it as ``Authorization: Bearer ...``.
"""

from __future__ import annotations

import logging
from typing import Annotated, Any

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    Response,
    status,
)
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.services.auth import (
    AuthError,
    AuthService,
    User,
    issue_session_token,
)
from backend.services.auth.dependencies import (
    SESSION_COOKIE,
    get_current_user,
)
from backend.services.auth.google_oauth import (
    OAuthError,
    get_oauth_client,
    is_configured as google_is_configured,
)
from backend.services.auth.magic_link import (
    MagicLinkError,
    build_link_url,
    issue_token as issue_magic_token,
    send_magic_link_email,
    verify_token as verify_magic_token,
)
from backend.services.db import get_session, is_db_configured

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _require_db() -> None:
    if not is_db_configured():
        raise HTTPException(
            status_code=503,
            detail="Auth disabled: AQ_DATABASE_URL is not configured.",
        )


def _user_payload(user: User) -> dict[str, Any]:
    """Public user shape returned to the SPA."""
    return {
        "id": user.id,
        "email": user.email,
        "tier": user.tier,
        "display_name": user.display_name,
        "email_verified": user.email_verified,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


def _set_session_cookie(response: Response, token: str) -> None:
    """Set the JWT as an HTTP-only cookie used by browser clients."""
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=settings.jwt_access_ttl_seconds,
        httponly=True,
        # ``secure`` is environment-dependent; set explicitly via setup later.
        secure=False,
        samesite="lax",
        path="/",
    )


def _clear_session_cookie(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/")


def _issue_session(user: User) -> str:
    return issue_session_token(user_id=user.id, email=user.email, tier=user.tier)


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class RegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr
    password: str = Field(min_length=8, max_length=256)
    display_name: str | None = Field(default=None, max_length=120)


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr
    password: str


class MagicLinkSendRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr


class MagicLinkVerifyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    token: str


# ---------------------------------------------------------------------------
# Email/password
# ---------------------------------------------------------------------------


@router.post("/email/register", status_code=201)
async def register_email(
    body: RegisterRequest,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    _require_db()
    auth = AuthService(session)
    try:
        user = await auth.register_email_password(
            email=body.email, password=body.password,
            display_name=body.display_name,
        )
    except AuthError as e:
        if e.code == "email_taken":
            raise HTTPException(status_code=409, detail=e.code) from e
        raise HTTPException(status_code=400, detail={"error": e.code, "message": str(e)}) from e
    await session.commit()

    token = _issue_session(user)
    _set_session_cookie(response, token)
    return {"user": _user_payload(user), "token": token}


@router.post("/email/login")
async def login_email(
    body: LoginRequest,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    _require_db()
    auth = AuthService(session)
    try:
        user = await auth.login_email_password(
            email=body.email, password=body.password,
        )
    except AuthError as e:
        raise HTTPException(
            status_code=401,
            detail={"error": e.code, "message": str(e)},
        ) from e
    await session.commit()

    token = _issue_session(user)
    _set_session_cookie(response, token)
    return {"user": _user_payload(user), "token": token}


# ---------------------------------------------------------------------------
# Magic link
# ---------------------------------------------------------------------------


@router.post("/magic-link/send")
async def magic_link_send(
    body: MagicLinkSendRequest,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Issue + send a magic link. Always returns 200 to avoid email enumeration."""
    _require_db()
    if not settings.magic_link_secret:
        raise HTTPException(
            status_code=503,
            detail="Magic link disabled: AQ_MAGIC_LINK_SECRET not set.",
        )
    try:
        token = issue_magic_token(body.email)
    except MagicLinkError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    link = build_link_url(token)
    delivery = await send_magic_link_email(to_email=body.email, link=link)
    # Don't leak whether the email exists in the DB.
    response_body: dict[str, Any] = {"sent": True}
    if not delivery.get("delivered") and delivery.get("fallback") == "stderr":
        # Dev convenience: surface the link in the response when no email
        # provider is configured. NEVER do this in prod.
        response_body["dev_link"] = link
    return response_body


@router.post("/magic-link/verify")
async def magic_link_verify(
    body: MagicLinkVerifyRequest,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    _require_db()
    try:
        email = verify_magic_token(body.token)
    except MagicLinkError as e:
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid_token", "message": str(e)},
        ) from e

    auth = AuthService(session)
    user = await auth.upsert_magic_link_user(email=email)
    await session.commit()

    token = _issue_session(user)
    _set_session_cookie(response, token)
    return {"user": _user_payload(user), "token": token}


# ---------------------------------------------------------------------------
# Google OAuth
# ---------------------------------------------------------------------------


@router.get("/google/start")
async def google_start(request: Request) -> Any:
    if not google_is_configured():
        raise HTTPException(
            status_code=503,
            detail="Google OAuth is not configured.",
        )
    oauth = get_oauth_client()
    redirect_uri = settings.google_oauth_redirect_url
    return await oauth.google.authorize_redirect(request, redirect_uri)


@router.get("/google/callback")
async def google_callback(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> RedirectResponse:
    """Browser-facing OAuth callback. Always responds with a 302 redirect to
    the frontend so the user lands somewhere usable; the session cookie is
    attached to the redirect response.
    """
    _require_db()
    frontend_base = (settings.magic_link_base_url or "http://localhost:3000").rstrip("/")
    if not google_is_configured():
        return RedirectResponse(f"{frontend_base}/auth/login?error=google_disabled", status_code=302)

    oauth = get_oauth_client()
    try:
        token = await oauth.google.authorize_access_token(request)
    except OAuthError as e:
        logger.warning("Google OAuth exchange failed: %s", e)
        return RedirectResponse(f"{frontend_base}/auth/login?error=oauth_failed", status_code=302)
    except Exception:
        logger.exception("Google OAuth callback crashed")
        return RedirectResponse(f"{frontend_base}/auth/login?error=oauth_failed", status_code=302)

    userinfo = token.get("userinfo") or {}
    sub = str(userinfo.get("sub") or "")
    email = str(userinfo.get("email") or "")
    if not sub or not email:
        logger.warning("Google OAuth callback: missing sub/email in userinfo")
        return RedirectResponse(f"{frontend_base}/auth/login?error=oauth_userinfo", status_code=302)

    auth = AuthService(session)
    user = await auth.upsert_google_user(
        google_sub=sub,
        email=email,
        display_name=userinfo.get("name"),
        email_verified=bool(userinfo.get("email_verified", True)),
    )
    await session.commit()

    jwt_token = _issue_session(user)
    redirect = RedirectResponse(f"{frontend_base}/", status_code=302)
    redirect.set_cookie(
        SESSION_COOKIE,
        jwt_token,
        max_age=settings.jwt_access_ttl_seconds,
        httponly=True,
        secure=False,
        samesite="lax",
        path="/",
    )
    return redirect


# ---------------------------------------------------------------------------
# Session
# ---------------------------------------------------------------------------


@router.get("/me")
async def me(user: Annotated[User, Depends(get_current_user)]) -> dict[str, Any]:
    return {"user": _user_payload(user)}


@router.post("/logout")
async def logout(response: Response) -> dict[str, Any]:
    _clear_session_cookie(response)
    return {"ok": True}
