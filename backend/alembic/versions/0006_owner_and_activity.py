"""Add the owner of an item and the activity log.

``items.owner`` holds the name of the person in the house who owns the thing.
It is free text, not an account, because the children and the housemates do
not sign in.

``activity`` holds one line for each change: who did it, what changed, and
when.

Revision ID: 0006
Revises: 0005
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the activity table and add the owner column."""
    op.create_table(
        "activity",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("entity_type", sa.String(length=20), nullable=False),
        sa.Column("entity_id", sa.UUID(), nullable=False),
        sa.Column("action", sa.String(length=30), nullable=False),
        sa.Column("summary", sa.String(length=300), nullable=False),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("actor", sa.String(length=150), nullable=True),
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_activity_deleted_at"), "activity", ["deleted_at"], unique=False
    )
    op.create_index(
        "ix_activity_entity",
        "activity",
        ["entity_type", "entity_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_activity_user_time", "activity", ["user_id", "created_at"], unique=False
    )

    op.add_column("items", sa.Column("owner", sa.String(length=150), nullable=True))
    op.create_index(op.f("ix_items_owner"), "items", ["owner"], unique=False)


def downgrade() -> None:
    """Drop the owner column and the activity table."""
    op.drop_index(op.f("ix_items_owner"), table_name="items")
    op.drop_column("items", "owner")
    op.drop_index("ix_activity_user_time", table_name="activity")
    op.drop_index("ix_activity_entity", table_name="activity")
    op.drop_index(op.f("ix_activity_deleted_at"), table_name="activity")
    op.drop_table("activity")
