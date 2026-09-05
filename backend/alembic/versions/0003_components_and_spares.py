"""Add components, fitted components, and spares.

Three tables. ``components`` is the catalogue of parts, with the default
price. ``item_components`` is one part fitted to one item, with its own price,
its serial number, and its notes. ``component_spares`` is stock on the shelf,
with a level that asks you to buy more.

Revision ID: 0003
Revises: 0002
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the three tables."""
    op.create_table(
        "components",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("brand", sa.String(length=150), nullable=True),
        sa.Column("model_number", sa.String(length=150), nullable=True),
        sa.Column("category", sa.String(length=100), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("default_price", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column(
            "is_consumable", sa.Boolean(), server_default="false", nullable=False
        ),
        sa.Column(
            "id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False
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
        op.f("ix_components_deleted_at"), "components", ["deleted_at"], unique=False
    )
    op.create_index(
        op.f("ix_components_is_consumable"),
        "components",
        ["is_consumable"],
        unique=False,
    )
    op.create_index(
        op.f("ix_components_model_number"), "components", ["model_number"], unique=False
    )
    op.create_index(
        "ix_components_user_category",
        "components",
        ["user_id", "category"],
        unique=False,
    )
    op.create_index(
        op.f("ix_components_user_id"), "components", ["user_id"], unique=False
    )
    op.create_index(
        "ix_components_user_name", "components", ["user_id", "name"], unique=False
    )
    op.create_table(
        "component_spares",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("component_id", sa.UUID(), nullable=False),
        sa.Column("location_id", sa.UUID(), nullable=True),
        sa.Column("quantity", sa.Integer(), server_default="0", nullable=False),
        sa.Column("minimum_quantity", sa.Integer(), server_default="0", nullable=False),
        sa.Column("unit_price", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False
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
        sa.CheckConstraint("quantity >= 0", name="ck_spares_quantity"),
        sa.ForeignKeyConstraint(
            ["component_id"], ["components.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["location_id"], ["locations.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "component_id", "location_id", name="uq_spares_component_location"
        ),
    )
    op.create_index(
        op.f("ix_component_spares_component_id"),
        "component_spares",
        ["component_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_component_spares_deleted_at"),
        "component_spares",
        ["deleted_at"],
        unique=False,
    )
    op.create_index("ix_spares_user", "component_spares", ["user_id"], unique=False)
    op.create_table(
        "item_components",
        sa.Column("item_id", sa.UUID(), nullable=False),
        sa.Column("component_id", sa.UUID(), nullable=False),
        sa.Column("quantity", sa.Integer(), server_default="1", nullable=False),
        sa.Column("price", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("serial_number", sa.String(length=150), nullable=True),
        sa.Column("fitted_on", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False
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
        sa.CheckConstraint("quantity > 0", name="ck_item_components_quantity"),
        sa.ForeignKeyConstraint(
            ["component_id"], ["components.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["item_id"], ["items.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_item_components_component_id"),
        "item_components",
        ["component_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_item_components_deleted_at"),
        "item_components",
        ["deleted_at"],
        unique=False,
    )
    op.create_index(
        "ix_item_components_item", "item_components", ["item_id"], unique=False
    )


def downgrade() -> None:
    """Drop them again."""
    op.drop_index("ix_item_components_item", table_name="item_components")
    op.drop_index(op.f("ix_item_components_deleted_at"), table_name="item_components")
    op.drop_index(op.f("ix_item_components_component_id"), table_name="item_components")
    op.drop_table("item_components")
    op.drop_index("ix_spares_user", table_name="component_spares")
    op.drop_index(op.f("ix_component_spares_deleted_at"), table_name="component_spares")
    op.drop_index(
        op.f("ix_component_spares_component_id"), table_name="component_spares"
    )
    op.drop_table("component_spares")
    op.drop_index("ix_components_user_name", table_name="components")
    op.drop_index(op.f("ix_components_user_id"), table_name="components")
    op.drop_index("ix_components_user_category", table_name="components")
    op.drop_index(op.f("ix_components_model_number"), table_name="components")
    op.drop_index(op.f("ix_components_is_consumable"), table_name="components")
    op.drop_index(op.f("ix_components_deleted_at"), table_name="components")
    op.drop_table("components")
