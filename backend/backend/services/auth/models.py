"""SQLAlchemy ORM models for users + identity providers.

Schema design notes:

- A ``User`` has an email (unique) and a ``tier`` ("free" or "pro"). Email is
  the canonical identity; whether the user authenticates by password, magic
  link, or Google OAuth is a separate ``IdentityProvider`` row.
- Multiple identity providers can map to the same user (e.g. someone signs
  up with email/password and later links Google). We enforce at most one
  identity row per (user, kind).
- ``password_hash`` lives on ``User`` for convenience, since email/password is
  the most common auth and avoids a join. Magic-link / Google users have
  ``password_hash = None``.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal

from sqlalchemy import (
    DateTime,
    ForeignKey,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.services.db import Base

# Tier values are used in code as plain strings for ergonomics; the DB
# constraint is a CHECK in the migration to keep the ORM unopinionated.
Tier = Literal["free", "pro"]


class IdentityKind(str, Enum):
    """How a user authenticates. One row per kind per user."""

    EMAIL_PASSWORD = "email_password"
    MAGIC_LINK = "magic_link"
    GOOGLE = "google"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True, nullable=False, index=True)
    # null for users created via OAuth / magic link only
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    tier: Mapped[str] = mapped_column(String(16), nullable=False, default="free")
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    email_verified: Mapped[bool] = mapped_column(default=False, nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
        onupdate=func.now(), nullable=False,
    )
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    identities: Mapped[list["IdentityProvider"]] = relationship(
        back_populates="user", cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<User id={self.id} email={self.email!r} tier={self.tier}>"


class IdentityProvider(Base):
    """One row per (user, auth method) — supports linking multiple providers."""

    __tablename__ = "identity_providers"
    __table_args__ = (
        UniqueConstraint("user_id", "kind", name="uq_identity_user_kind"),
        UniqueConstraint("kind", "external_id", name="uq_identity_kind_external"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    # Stored as plain string to keep the migration framework-agnostic.
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    # Provider-specific identifier:
    #   email_password → email (lowercased, mirrors User.email)
    #   magic_link    → email
    #   google        → Google ``sub`` claim (stable across email changes)
    external_id: Mapped[str] = mapped_column(String(254), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    user: Mapped["User"] = relationship(back_populates="identities")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<IdentityProvider user_id={self.user_id} kind={self.kind}>"
