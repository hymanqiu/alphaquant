"""Magic-link auth provider.

Stateless token-based flow:

1. User requests a link by submitting email.
2. We mint an ``itsdangerous``-signed token containing the email + a salt.
   The token is sent via email and is single-use only by virtue of its
   short TTL — we don't store/revoke per-token (that requires a DB table
   we don't need for the MVP).
3. User clicks the link → frontend submits the token → we verify the
   signature + freshness + email match, then issue a session JWT.

The email send goes through Resend's HTTP API when ``AQ_RESEND_API_KEY`` is
set; otherwise we just log the link to stderr (developer-friendly fallback).
"""

from __future__ import annotations

import logging
from typing import Any

import httpx
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from backend.config import settings

logger = logging.getLogger(__name__)


_SALT = "alphaquant.magic-link.v1"


class MagicLinkError(Exception):
    """Token couldn't be verified, expired, or didn't match."""


def _serializer() -> URLSafeTimedSerializer:
    if not settings.magic_link_secret:
        raise MagicLinkError("AQ_MAGIC_LINK_SECRET not configured")
    return URLSafeTimedSerializer(settings.magic_link_secret, salt=_SALT)


def issue_token(email: str) -> str:
    """Mint a signed magic-link token bound to *email*."""
    normalized = email.strip().lower()
    if "@" not in normalized:
        raise MagicLinkError(f"invalid email: {email!r}")
    return _serializer().dumps({"email": normalized})


def verify_token(token: str) -> str:
    """Verify a token and return the bound email.

    Raises :class:`MagicLinkError` for any failure (bad signature, expired,
    malformed payload).
    """
    try:
        payload = _serializer().loads(
            token, max_age=settings.magic_link_ttl_seconds,
        )
    except SignatureExpired as e:
        raise MagicLinkError("magic link expired") from e
    except BadSignature as e:
        raise MagicLinkError("invalid magic link") from e

    if not isinstance(payload, dict) or "email" not in payload:
        raise MagicLinkError("malformed payload")
    email = str(payload["email"]).strip().lower()
    if "@" not in email:
        raise MagicLinkError("malformed email in payload")
    return email


def build_link_url(token: str) -> str:
    """Construct the user-facing URL embedded in the email."""
    base = (settings.magic_link_base_url or "http://localhost:3000").rstrip("/")
    return f"{base}/auth/magic-link/verify?token={token}"


# ---------------------------------------------------------------------------
# Email send (Resend HTTP API; stderr fallback when key missing)
# ---------------------------------------------------------------------------


_RESEND_URL = "https://api.resend.com/emails"


async def send_magic_link_email(*, to_email: str, link: str) -> dict[str, Any]:
    """Send the magic-link email. Returns provider response or fallback dict.

    When ``AQ_RESEND_API_KEY`` is empty, this logs the link to stderr and
    returns ``{"delivered": False, "fallback": "stderr"}`` — useful in dev
    without configuring an email provider.
    """
    subject = "Your AlphaQuant sign-in link"
    body_text = (
        f"Click the link below to sign in to AlphaQuant.\n\n"
        f"{link}\n\n"
        f"This link expires in {settings.magic_link_ttl_seconds // 60} minutes. "
        f"If you didn't request it, you can ignore this message."
    )

    if not settings.resend_api_key:
        # Dev fallback — print the link prominently so the developer can copy it.
        logger.warning(
            "magic_link_dev_fallback to=%s link=%s",
            to_email, link,
        )
        return {"delivered": False, "fallback": "stderr", "link": link}

    payload = {
        "from": settings.resend_from_email,
        "to": [to_email],
        "subject": subject,
        "text": body_text,
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.post(
                _RESEND_URL,
                headers={
                    "Authorization": f"Bearer {settings.resend_api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            resp.raise_for_status()
        except (httpx.HTTPStatusError, httpx.RequestError) as e:
            logger.warning("Resend email send failed for %s: %s", to_email, e)
            return {"delivered": False, "error": str(e)}

    data = resp.json() if resp.content else {}
    return {"delivered": True, "provider": "resend", "id": data.get("id")}
