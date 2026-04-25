"""Google OAuth2 provider (authorization-code flow).

Uses ``authlib``'s starlette integration to handle the OAuth dance. The flow:

1. ``GET /api/auth/google/start`` — we redirect the browser to Google with
   a CSRF-protected state.
2. Google redirects back to ``AQ_GOOGLE_OAUTH_REDIRECT_URL`` with an auth
   code → ``GET /api/auth/google/callback`` exchanges it for tokens, fetches
   the userinfo, then upserts the user via ``AuthService.upsert_google_user``
   and issues our JWT session cookie.

We deliberately keep this module thin and stateless — no per-OAuth-client
caching beyond what authlib does. Configure once, reuse via
``get_oauth_client()``.
"""

from __future__ import annotations

import logging

from authlib.integrations.starlette_client import OAuth, OAuthError

from backend.config import settings

logger = logging.getLogger(__name__)


class GoogleOAuthError(Exception):
    """OAuth flow failed at some step (config, exchange, userinfo)."""


_oauth: OAuth | None = None


def is_configured() -> bool:
    return bool(
        settings.google_oauth_client_id
        and settings.google_oauth_client_secret
        and settings.google_oauth_redirect_url
    )


def get_oauth_client() -> OAuth:
    """Return the lazily-initialized authlib OAuth registry with Google."""
    global _oauth
    if _oauth is None:
        if not is_configured():
            raise GoogleOAuthError(
                "Google OAuth is not configured: set "
                "AQ_GOOGLE_OAUTH_CLIENT_ID / SECRET / REDIRECT_URL"
            )
        oauth = OAuth()
        oauth.register(
            name="google",
            client_id=settings.google_oauth_client_id,
            client_secret=settings.google_oauth_client_secret,
            server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
            client_kwargs={
                "scope": "openid email profile",
                "prompt": "select_account",
            },
        )
        _oauth = oauth
    return _oauth


# Re-export OAuthError under our namespace so callers don't import authlib.
__all__ = ["GoogleOAuthError", "OAuthError", "get_oauth_client", "is_configured"]
