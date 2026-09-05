"""Add the photos table.

One table holds the photographs of a component and of a cable. ``owner_type``
names the table that each row belongs to, so a third kind of owner needs no
new table. An item keeps its own ``item_photos``, because an item photograph
also carries the OCR text.

Revision ID: 0005
Revises: 0004
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the photos table."""
    op.create_table(
        "photos",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("owner_type", sa.String(length=20), nullable=False),
        sa.Column("owner_id", sa.UUID(), nullable=False),
        sa.Column("file_path", sa.String(length=500), nullable=False),
        sa.Column("thumbnail_path", sa.String(length=500), nullable=True),
        sa.Column("is_primary", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("caption", sa.String(length=300), nullable=True),
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
        op.f("ix_photos_deleted_at"), "photos", ["deleted_at"], unique=False
    )
    op.create_index(
        "ix_photos_owner", "photos", ["owner_type", "owner_id"], unique=False
    )
    op.create_index("ix_photos_user", "photos", ["user_id"], unique=False)


def downgrade() -> None:
    """Drop the photos table."""
    op.drop_index("ix_photos_user", table_name="photos")
    op.drop_index("ix_photos_owner", table_name="photos")
    op.drop_index(op.f("ix_photos_deleted_at"), table_name="photos")
    op.drop_table("photos")
