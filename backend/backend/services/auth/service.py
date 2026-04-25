"""High-level auth service — provider-agnostic orchestration.

Each ``providers/*.py`` module knows how to verify a credential (password,
magic-link token, Google OAuth code). They all funnel into ``AuthService``,
which is responsible for:

- Looking up / upserting the ``User`` row by email.
- Recording the ``IdentityProvider`` row for that auth method.
- Updating ``last_login_at`` etc.
- Returning the authenticated ``User``.

This keeps each provider's code small and focused on its own protocol.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings

from .models import IdentityKind, IdentityProvider, User
from .passwords import hash_password, verify_password

logger = logging.getLogger(__name__)


class AuthError(Exception):
    """Raised by AuthService for user-facing auth failures.

    Always carries a stable ``code`` field that routes can map to HTTP
    statuses without leaking internal detail.
    """

    def __init__(self, code: str, message: str | None = None) -> None:
        super().__init__(message or code)
        self.code = code


class AuthService:
    """Stateless helper bound to an ``AsyncSession``."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ------------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------------

    async def get_by_id(self, user_id: int) -> User | None:
        return await self._session.get(User, user_id)

    async def get_by_email(self, email: str) -> User | None:
        normalized = (email or "").strip().lower()
        if not normalized:
            return None
        result = await self._session.execute(
            select(User).where(User.email == normalized)
        )
        return result.scalar_one_or_none()

    async def get_identity(
        self, *, kind: IdentityKind, external_id: str,
    ) -> IdentityProvider | None:
        result = await self._session.execute(
            select(IdentityProvider).where(
                IdentityProvider.kind == kind.value,
                IdentityProvider.external_id == external_id,
            )
        )
        return result.scalar_one_or_none()

    # ------------------------------------------------------------------
    # Email + password
    # ------------------------------------------------------------------

    async def register_email_password(
        self, *, email: str, password: str, display_name: str | None = None,
    ) -> User:
        normalized = email.strip().lower()
        existing = await self.get_by_email(normalized)
        if existing is not None:
            raise AuthError("email_taken", f"{normalized} is already registered")

        try:
            digest = hash_password(password)
        except ValueError as e:
            raise AuthError("weak_password", str(e)) from e

        user = User(
            email=normalized,
            password_hash=digest,
            tier=settings.default_user_tier or "free",
            display_name=display_name or None,
            email_verified=False,
        )
        self._session.add(user)
        await self._session.flush()  # populate user.id

        identity = IdentityProvider(
            user_id=user.id,
            kind=IdentityKind.EMAIL_PASSWORD.value,
            external_id=normalized,
        )
        self._session.add(identity)
        await self._session.flush()
        return user

    async def login_email_password(self, *, email: str, password: str) -> User:
        user = await self.get_by_email(email)
        # Always run bcrypt to avoid a timing oracle on user existence.
        verified = verify_password(password, user.password_hash if user else None)
        if user is None or not verified or not user.is_active:
            raise AuthError("invalid_credentials", "Email or password is incorrect")
        await self._mark_login(user, IdentityKind.EMAIL_PASSWORD, email.strip().lower())
        return user

    # ------------------------------------------------------------------
    # Magic link
    # ------------------------------------------------------------------

    async def upsert_magic_link_user(
        self, *, email: str, display_name: str | None = None,
    ) -> User:
        """Create or fetch a user by email, link the magic-link identity."""
        normalized = email.strip().lower()
        user = await self.get_by_email(normalized)
        if user is None:
            user = User(
                email=normalized,
                password_hash=None,
                tier=settings.default_user_tier or "free",
                display_name=display_name or None,
                email_verified=True,  # magic link proves email control
            )
            self._session.add(user)
            await self._session.flush()
        elif not user.email_verified:
            user.email_verified = True
        await self._link_identity(user, IdentityKind.MAGIC_LINK, normalized)
        await self._mark_login(user, IdentityKind.MAGIC_LINK, normalized)
        return user

    # ------------------------------------------------------------------
    # Google OAuth
    # ------------------------------------------------------------------

    async def upsert_google_user(
        self,
        *,
        google_sub: str,
        email: str,
        display_name: str | None = None,
        email_verified: bool = True,
    ) -> User:
        """Resolve / create a user from a verified Google identity.

        We key on the Google ``sub`` (stable across email changes) but match
        existing users by email when no Google identity is yet linked.
        """
        existing_identity = await self.get_identity(
            kind=IdentityKind.GOOGLE, external_id=google_sub,
        )
        if existing_identity is not None:
            user = await self.get_by_id(existing_identity.user_id)
            if user is None:
                # Identity row dangling; clean up and recreate
                await self._session.delete(existing_identity)
            elif user.is_active:
                await self._mark_login(user, IdentityKind.GOOGLE, google_sub)
                return user

        normalized_email = email.strip().lower()
        user = await self.get_by_email(normalized_email)
        if user is None:
            user = User(
                email=normalized_email,
                password_hash=None,
                tier=settings.default_user_tier or "free",
                display_name=display_name or None,
                email_verified=email_verified,
            )
            self._session.add(user)
            await self._session.flush()
        else:
            if not user.email_verified and email_verified:
                user.email_verified = True
            if not user.display_name and display_name:
                user.display_name = display_name

        await self._link_identity(user, IdentityKind.GOOGLE, google_sub)
        await self._mark_login(user, IdentityKind.GOOGLE, google_sub)
        return user

    # ------------------------------------------------------------------
    # Tier management
    # ------------------------------------------------------------------

    async def set_tier(self, user: User, *, tier: Literal["free", "pro"]) -> User:
        if tier not in {"free", "pro"}:
            raise AuthError("invalid_tier", f"Unknown tier: {tier!r}")
        user.tier = tier
        await self._session.flush()
        return user

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _link_identity(
        self, user: User, kind: IdentityKind, external_id: str,
    ) -> None:
        existing = await self._session.execute(
            select(IdentityProvider).where(
                IdentityProvider.user_id == user.id,
                IdentityProvider.kind == kind.value,
            )
        )
        row = existing.scalar_one_or_none()
        if row is not None:
            row.external_id = external_id
            return
        identity = IdentityProvider(
            user_id=user.id, kind=kind.value, external_id=external_id,
        )
        self._session.add(identity)
        await self._session.flush()

    async def _mark_login(
        self, user: User, kind: IdentityKind, external_id: str,
    ) -> None:
        now = datetime.now(timezone.utc)
        user.last_login_at = now
        # Update identity last_used_at if it exists
        result = await self._session.execute(
            select(IdentityProvider).where(
                IdentityProvider.user_id == user.id,
                IdentityProvider.kind == kind.value,
                IdentityProvider.external_id == external_id,
            )
        )
        identity = result.scalar_one_or_none()
        if identity is not None:
            identity.last_used_at = now
