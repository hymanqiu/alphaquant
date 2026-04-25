"""Authentication module — pluggable providers + JWT sessions.

Public surface (everything else is internal):

- ``User`` / ``IdentityProvider`` / ``Tier`` — ORM types
- ``passwords.hash_password / verify_password``
- ``tokens.issue_session_token / decode_session_token``
- ``providers.email_password`` / ``providers.magic_link`` / ``providers.google_oauth``
- ``dependencies.get_current_user`` / ``dependencies.require_pro``
- ``service.AuthService`` — high-level register / login / upsert helpers
"""

from .dependencies import (
    get_current_user,
    get_optional_user,
    require_admin_tier,
    require_pro,
)
from .models import IdentityProvider, Tier, User
from .passwords import hash_password, verify_password
from .service import AuthError, AuthService
from .tokens import (
    SessionTokenError,
    decode_session_token,
    issue_session_token,
)

__all__ = [
    "AuthError",
    "AuthService",
    "IdentityProvider",
    "SessionTokenError",
    "Tier",
    "User",
    "decode_session_token",
    "get_current_user",
    "get_optional_user",
    "hash_password",
    "issue_session_token",
    "require_admin_tier",
    "require_pro",
    "verify_password",
]
