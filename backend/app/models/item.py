"""The item model, its photos, and the full-text search index."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    Computed,
    Date,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, SyncMixin, TimestampMixin, UUIDMixin
from app.models.tag import item_tags

if TYPE_CHECKING:
    from app.models.custom_field import CustomField
    from app.models.location import Location
    from app.models.maintenance import MaintenanceLog
    from app.models.nfc import NfcTag
    from app.models.receipt import ReceiptItem
    from app.models.tag import Tag
    from app.models.user import User

ITEM_CONDITIONS = ("new", "good", "fair", "poor")

# The expression behind the generated search column. PostgreSQL keeps this
# value current on every write, so no application code has to maintain it.
SEARCH_EXPRESSION = (
    "to_tsvector('english', "
    "coalesce(name, '') || ' ' || "
    "coalesce(description, '') || ' ' || "
    "coalesce(brand, '') || ' ' || "
    "coalesce(model, '') || ' ' || "
    "coalesce(notes, ''))"
)


class Item(UUIDMixin, TimestampMixin, SyncMixin, Base):
    """One thing that the household owns."""

    __tablename__ = "items"
    __table_args__ = (
        Index("ix_items_user_location", "user_id", "location_id"),
        Index("ix_items_search_vector", "search_vector", postgresql_using="gin"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # A deleted location must not delete the items inside it. The items
    # become unplaced, and the user files them again.
    location_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("locations.id", ondelete="SET NULL"),
        nullable=True,
    )

    name: Mapped[str] = mapped_column(String(300), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    subcategory: Mapped[str | None] = mapped_column(String(100), nullable=True)
    brand: Mapped[str | None] = mapped_column(String(150), nullable=True)
    model: Mapped[str | None] = mapped_column(String(150), nullable=True)
    serial_number: Mapped[str | None] = mapped_column(String(150), nullable=True)
    barcode: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    purchase_price: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2), nullable=True
    )
    current_value: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2), nullable=True
    )
    purchase_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    purchase_location: Mapped[str | None] = mapped_column(String(200), nullable=True)
    warranty_expires: Mapped[date | None] = mapped_column(
        Date, nullable=True, index=True
    )

    condition: Mapped[str | None] = mapped_column(String(20), nullable=True)
    quantity: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    is_lent: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false", index=True
    )
    lent_to: Mapped[str | None] = mapped_column(String(200), nullable=True)
    lent_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    search_vector: Mapped[str | None] = mapped_column(
        TSVECTOR, Computed(SEARCH_EXPRESSION, persisted=True), nullable=True
    )

    user: Mapped[User] = relationship(back_populates="items")
    location: Mapped[Location | None] = relationship(back_populates="items")
    photos: Mapped[list[ItemPhoto]] = relationship(
        back_populates="item",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="ItemPhoto.is_primary.desc(), ItemPhoto.created_at",
    )
    tags: Mapped[list[Tag]] = relationship(
        secondary=item_tags, back_populates="items"
    )
    maintenance_logs: Mapped[list[MaintenanceLog]] = relationship(
        back_populates="item", cascade="all, delete-orphan", passive_deletes=True
    )
    custom_fields: Mapped[list[CustomField]] = relationship(
        back_populates="item", cascade="all, delete-orphan", passive_deletes=True
    )
    nfc_tags: Mapped[list[NfcTag]] = relationship(
        back_populates="item", cascade="all, delete-orphan", passive_deletes=True
    )
    receipt_items: Mapped[list[ReceiptItem]] = relationship(
        back_populates="item", passive_deletes=True
    )

    def __repr__(self) -> str:
        return f"<Item {self.name}>"


class ItemPhoto(UUIDMixin, TimestampMixin, Base):
    """One photograph of an item.

    ``thumbnail_path`` points at the smallest generated size. The larger sizes
    sit beside it in the same directory, named with their pixel width. See the
    upload conventions in CLAUDE.md.
    """

    __tablename__ = "item_photos"

    item_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    thumbnail_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_primary: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    ai_description: Mapped[str | None] = mapped_column(Text, nullable=True)

    item: Mapped[Item] = relationship(back_populates="photos")

    def __repr__(self) -> str:
        return f"<ItemPhoto {self.file_path}>"
