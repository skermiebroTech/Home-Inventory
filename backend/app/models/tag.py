"""Tags and the item-to-tag association table."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Column, ForeignKey, String, Table
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.item import Item

item_tags = Table(
    "item_tags",
    Base.metadata,
    Column(
        "item_id",
        PgUUID(as_uuid=True),
        ForeignKey("items.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "tag_id",
        PgUUID(as_uuid=True),
        ForeignKey("tags.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class Tag(UUIDMixin, TimestampMixin, Base):
    """A label that groups items. Tags are shared across the household."""

    __tablename__ = "tags"

    name: Mapped[str] = mapped_column(
        String(80), nullable=False, unique=True, index=True
    )
    color: Mapped[str] = mapped_column(
        String(9), nullable=False, default="#64748b", server_default="#64748b"
    )

    items: Mapped[list[Item]] = relationship(secondary=item_tags, back_populates="tags")

    def __repr__(self) -> str:
        return f"<Tag {self.name}>"
