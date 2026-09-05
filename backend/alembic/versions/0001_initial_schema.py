"""Initial schema.

Creates every table in the architecture specification, plus two columns that
the delta sync contract needs: ``version`` and ``deleted_at``.

Revision ID: 0001
Revises:
Create Date: 2026-09-05
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# PostgreSQL keeps this column current on every write. No application code
# maintains it. It must match SEARCH_EXPRESSION in app/models/item.py.
SEARCH_EXPRESSION = (
    "to_tsvector('english', "
    "coalesce(name, '') || ' ' || "
    "coalesce(description, '') || ' ' || "
    "coalesce(brand, '') || ' ' || "
    "coalesce(model, '') || ' ' || "
    "coalesce(notes, ''))"
)


def _uuid_pk() -> sa.Column:
    return sa.Column(
        "id",
        postgresql.UUID(as_uuid=True),
        server_default=sa.text("gen_random_uuid()"),
        nullable=False,
    )


def _timestamps() -> list[sa.Column]:
    return [
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
    ]


def _sync_columns() -> list[sa.Column]:
    return [
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    ]


def upgrade() -> None:
    # --- users ---
    op.create_table(
        "users",
        _uuid_pk(),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=20), server_default="user", nullable=False),
        sa.Column(
            "is_active", sa.Boolean(), server_default="true", nullable=False
        ),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # --- tags ---
    op.create_table(
        "tags",
        _uuid_pk(),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column(
            "color", sa.String(length=9), server_default="#64748b", nullable=False
        ),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tags_name", "tags", ["name"], unique=True)

    # --- locations ---
    op.create_table(
        "locations",
        _uuid_pk(),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("parent_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("type", sa.String(length=20), server_default="room", nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("photo_path", sa.String(length=500), nullable=True),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        *_sync_columns(),
        *_timestamps(),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parent_id"], ["locations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_locations_user_id", "locations", ["user_id"])
    op.create_index("ix_locations_deleted_at", "locations", ["deleted_at"])
    op.create_index(
        "ix_locations_user_parent", "locations", ["user_id", "parent_id"]
    )

    # --- items ---
    op.create_table(
        "items",
        _uuid_pk(),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("location_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("name", sa.String(length=300), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", sa.String(length=100), nullable=True),
        sa.Column("subcategory", sa.String(length=100), nullable=True),
        sa.Column("brand", sa.String(length=150), nullable=True),
        sa.Column("model", sa.String(length=150), nullable=True),
        sa.Column("serial_number", sa.String(length=150), nullable=True),
        sa.Column("barcode", sa.String(length=64), nullable=True),
        sa.Column("purchase_price", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("current_value", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("purchase_date", sa.Date(), nullable=True),
        sa.Column("purchase_location", sa.String(length=200), nullable=True),
        sa.Column("warranty_expires", sa.Date(), nullable=True),
        sa.Column("condition", sa.String(length=20), nullable=True),
        sa.Column("quantity", sa.Integer(), server_default="1", nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_lent", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("lent_to", sa.String(length=200), nullable=True),
        sa.Column("lent_date", sa.Date(), nullable=True),
        sa.Column(
            "search_vector",
            postgresql.TSVECTOR(),
            sa.Computed(SEARCH_EXPRESSION, persisted=True),
            nullable=True,
        ),
        *_sync_columns(),
        *_timestamps(),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["location_id"], ["locations.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_items_user_id", "items", ["user_id"])
    op.create_index("ix_items_name", "items", ["name"])
    op.create_index("ix_items_category", "items", ["category"])
    op.create_index("ix_items_barcode", "items", ["barcode"])
    op.create_index("ix_items_warranty_expires", "items", ["warranty_expires"])
    op.create_index("ix_items_is_lent", "items", ["is_lent"])
    op.create_index("ix_items_deleted_at", "items", ["deleted_at"])
    op.create_index("ix_items_user_location", "items", ["user_id", "location_id"])
    op.create_index(
        "ix_items_search_vector",
        "items",
        ["search_vector"],
        postgresql_using="gin",
    )

    # --- item_photos ---
    op.create_table(
        "item_photos",
        _uuid_pk(),
        sa.Column("item_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("file_path", sa.String(length=500), nullable=False),
        sa.Column("thumbnail_path", sa.String(length=500), nullable=True),
        sa.Column(
            "is_primary", sa.Boolean(), server_default="false", nullable=False
        ),
        sa.Column("ai_description", sa.Text(), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["item_id"], ["items.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_item_photos_item_id", "item_photos", ["item_id"])

    # --- item_tags ---
    op.create_table(
        "item_tags",
        sa.Column("item_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tag_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["item_id"], ["items.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tag_id"], ["tags.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("item_id", "tag_id"),
    )

    # --- receipts ---
    op.create_table(
        "receipts",
        _uuid_pk(),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("file_path", sa.String(length=500), nullable=False),
        sa.Column("thumbnail_path", sa.String(length=500), nullable=True),
        sa.Column("vendor", sa.String(length=200), nullable=True),
        sa.Column("purchase_date", sa.Date(), nullable=True),
        sa.Column("total_amount", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column(
            "currency", sa.String(length=3), server_default="AUD", nullable=False
        ),
        sa.Column("ocr_raw_text", sa.Text(), nullable=True),
        sa.Column("ocr_parsed_json", postgresql.JSONB(), nullable=True),
        *_sync_columns(),
        *_timestamps(),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_receipts_user_id", "receipts", ["user_id"])
    op.create_index("ix_receipts_vendor", "receipts", ["vendor"])
    op.create_index("ix_receipts_purchase_date", "receipts", ["purchase_date"])
    op.create_index("ix_receipts_deleted_at", "receipts", ["deleted_at"])

    # --- receipt_items ---
    op.create_table(
        "receipt_items",
        _uuid_pk(),
        sa.Column("receipt_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("item_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("line_text", sa.String(length=500), nullable=False),
        sa.Column("line_amount", sa.Numeric(precision=12, scale=2), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["receipt_id"], ["receipts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["item_id"], ["items.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_receipt_items_receipt_id", "receipt_items", ["receipt_id"])
    op.create_index("ix_receipt_items_item_id", "receipt_items", ["item_id"])

    # --- maintenance_logs ---
    op.create_table(
        "maintenance_logs",
        _uuid_pk(),
        sa.Column("item_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("date_performed", sa.Date(), nullable=True),
        sa.Column("next_due_date", sa.Date(), nullable=True),
        sa.Column("cost", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        *_sync_columns(),
        *_timestamps(),
        sa.ForeignKeyConstraint(["item_id"], ["items.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_maintenance_logs_item_id", "maintenance_logs", ["item_id"])
    op.create_index(
        "ix_maintenance_logs_next_due_date", "maintenance_logs", ["next_due_date"]
    )
    op.create_index(
        "ix_maintenance_logs_deleted_at", "maintenance_logs", ["deleted_at"]
    )

    # --- custom_fields ---
    op.create_table(
        "custom_fields",
        _uuid_pk(),
        sa.Column("item_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("field_name", sa.String(length=100), nullable=False),
        sa.Column("field_value", sa.Text(), nullable=True),
        *_sync_columns(),
        *_timestamps(),
        sa.ForeignKeyConstraint(["item_id"], ["items.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "item_id", "field_name", name="uq_custom_fields_item_name"
        ),
    )
    op.create_index("ix_custom_fields_item_id", "custom_fields", ["item_id"])
    op.create_index("ix_custom_fields_deleted_at", "custom_fields", ["deleted_at"])

    # --- nfc_tags ---
    op.create_table(
        "nfc_tags",
        _uuid_pk(),
        sa.Column("item_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("location_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("nfc_uid", sa.String(length=64), nullable=False),
        sa.Column("label", sa.String(length=200), nullable=True),
        *_timestamps(),
        sa.CheckConstraint(
            "(item_id IS NOT NULL AND location_id IS NULL)"
            " OR (item_id IS NULL AND location_id IS NOT NULL)",
            name="ck_nfc_tags_one_target",
        ),
        sa.ForeignKeyConstraint(["item_id"], ["items.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["location_id"], ["locations.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_nfc_tags_item_id", "nfc_tags", ["item_id"])
    op.create_index("ix_nfc_tags_location_id", "nfc_tags", ["location_id"])
    op.create_index("ix_nfc_tags_nfc_uid", "nfc_tags", ["nfc_uid"], unique=True)


def downgrade() -> None:
    op.drop_table("nfc_tags")
    op.drop_table("custom_fields")
    op.drop_table("maintenance_logs")
    op.drop_table("receipt_items")
    op.drop_table("receipts")
    op.drop_table("item_tags")
    op.drop_table("item_photos")
    op.drop_table("items")
    op.drop_table("locations")
    op.drop_table("tags")
    op.drop_table("users")
