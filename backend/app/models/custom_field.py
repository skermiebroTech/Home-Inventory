"""User defined fields on an item."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, SyncMixin, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.item import Item


class CustomField(UUIDMixin, TimestampMixin, SyncMixin, Base):
    """One extra named value on an item."""

    __tablename__ = "custom_fields"
    __table_args__ = (
        UniqueConstraint("item_id", "field_name", name="uq_custom_fields_item_name"),
    )

    item_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    field_name: Mapped[str] = mapped_column(String(100), nullable=False)
    field_value: Mapped[str | None] = mapped_column(Text, nullable=True)

    item: Mapped[Item] = relationship(back_populates="custom_fields")

    def __repr__(self) -> str:
        return f"<CustomField {self.field_name}>"
