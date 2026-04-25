"""init users + identity_providers

Revision ID: 0001_init_users
Revises:
Create Date: 2026-04-25

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001_init_users"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=True),
        sa.Column(
            "tier",
            sa.String(length=16),
            nullable=False,
            server_default=sa.text("'free'"),
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column(
            "email_verified",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("display_name", sa.String(length=120), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("email", name="uq_users_email"),
        sa.CheckConstraint(
            "tier IN ('free', 'pro', 'admin')",
            name="ck_users_tier",
        ),
    )
    op.create_index("ix_users_email", "users", ["email"])

    op.create_table(
        "identity_providers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("external_id", sa.String(length=254), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("user_id", "kind", name="uq_identity_user_kind"),
        sa.UniqueConstraint(
            "kind", "external_id", name="uq_identity_kind_external",
        ),
        sa.CheckConstraint(
            "kind IN ('email_password', 'magic_link', 'google')",
            name="ck_identity_kind",
        ),
    )
    op.create_index("ix_identity_providers_user_id", "identity_providers", ["user_id"])
    op.create_index("ix_identity_providers_external_id", "identity_providers", ["external_id"])


def downgrade() -> None:
    op.drop_index("ix_identity_providers_external_id", table_name="identity_providers")
    op.drop_index("ix_identity_providers_user_id", table_name="identity_providers")
    op.drop_table("identity_providers")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
