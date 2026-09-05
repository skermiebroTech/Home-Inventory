"""Add the cables table.

One table. A cable has two ends, a length, a count, and a place. It can also
name the item that it came with. That link empties when the item goes, and
the cable stays.

Revision ID: 0004
Revises: 0003
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the cables table."""
    op.create_table(
        "cables",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("kind", sa.String(length=100), nullable=True),
        sa.Column("connector_a", sa.String(length=80), nullable=True),
        sa.Column("connector_b", sa.String(length=80), nullable=True),
        sa.Column("length_cm", sa.Integer(), nullable=True),
        sa.Column("colour", sa.String(length=50), nullable=True),
        sa.Column("brand", sa.String(length=150), nullable=True),
        sa.Column("specification", sa.String(length=200), nullable=True),
        sa.Column("quantity", sa.Integer(), server_default="1", nullable=False),
        sa.Column("price", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("location_id", sa.UUID(), nullable=True),
        sa.Column("item_id", sa.UUID(), nullable=True),
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
        sa.CheckConstraint(
            "length_cm IS NULL OR length_cm >= 0", name="ck_cables_length"
        ),
        sa.CheckConstraint("quantity >= 0", name="ck_cables_quantity"),
        sa.ForeignKeyConstraint(["item_id"], ["items.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["location_id"], ["locations.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_cables_deleted_at"), "cables", ["deleted_at"], unique=False
    )
    op.create_index(op.f("ix_cables_item_id"), "cables", ["item_id"], unique=False)
    op.create_index(op.f("ix_cables_user_id"), "cables", ["user_id"], unique=False)
    op.create_index("ix_cables_user_kind", "cables", ["user_id", "kind"], unique=False)
    op.create_index("ix_cables_user_name", "cables", ["user_id", "name"], unique=False)


def downgrade() -> None:
    """Drop the cables table."""
    op.drop_index("ix_cables_user_name", table_name="cables")
    op.drop_index("ix_cables_user_kind", table_name="cables")
    op.drop_index(op.f("ix_cables_user_id"), table_name="cables")
    op.drop_index(op.f("ix_cables_item_id"), table_name="cables")
    op.drop_index(op.f("ix_cables_deleted_at"), table_name="cables")
    op.drop_table("cables")
