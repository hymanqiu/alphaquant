"""saved_theses + watchlist_items

Revision ID: 0002_saved_thesis_and_watchlist
Revises: 0001_init_users
Create Date: 2026-05-01

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0002_saved_thesis_and_watchlist"
down_revision: Union[str, None] = "0001_init_users"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "saved_theses",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("ticker", sa.String(length=8), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=True),
        sa.Column(
            "is_public",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column("hero_snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("components_snapshot", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_saved_theses_user_id", "saved_theses", ["user_id"])
    op.create_index("ix_saved_theses_ticker", "saved_theses", ["ticker"])

    op.create_table(
        "watchlist_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("ticker", sa.String(length=8), nullable=False),
        sa.Column("target_mos_pct", sa.Float(), nullable=True),
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
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_mos_pct", sa.Float(), nullable=True),
        sa.Column("last_signal", sa.String(length=32), nullable=True),
        sa.UniqueConstraint(
            "user_id", "ticker", name="uq_watchlist_user_ticker",
        ),
    )
    op.create_index(
        "ix_watchlist_items_user_id", "watchlist_items", ["user_id"],
    )
    op.create_index(
        "ix_watchlist_items_ticker", "watchlist_items", ["ticker"],
    )


def downgrade() -> None:
    op.drop_index("ix_watchlist_items_ticker", table_name="watchlist_items")
    op.drop_index("ix_watchlist_items_user_id", table_name="watchlist_items")
    op.drop_table("watchlist_items")
    op.drop_index("ix_saved_theses_ticker", table_name="saved_theses")
    op.drop_index("ix_saved_theses_user_id", table_name="saved_theses")
    op.drop_table("saved_theses")
