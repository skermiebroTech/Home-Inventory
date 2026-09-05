"""The location tree: rooms, then zones, then containers."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, SyncMixin, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.item import Item
    from app.models.nfc import NfcTag
    from app.models.user import User

LOCATION_TYPES = ("room", "zone", "container")


class Location(UUIDMixin, TimestampMixin, SyncMixin, Base):
    """A place that holds items. A location may hold other locations."""

    __tablename__ = "locations"
    __table_args__ = (
        Index("ix_locations_user_parent", "user_id", "parent_id"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("locations.id", ondelete="CASCADE"),
        nullable=True,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    type: Mapped[str] = mapped_column(
        String(20), nullable=False, default="room", server_default="room"
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    photo_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    sort_order: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )

    user: Mapped[User] = relationship(back_populates="locations")
    parent: Mapped[Location | None] = relationship(
        back_populates="children", remote_side="Location.id"
    )
    children: Mapped[list[Location]] = relationship(
        back_populates="parent", cascade="all, delete-orphan", passive_deletes=True
    )
    items: Mapped[list[Item]] = relationship(back_populates="location")
    nfc_tags: Mapped[list[NfcTag]] = relationship(
        back_populates="location", cascade="all, delete-orphan", passive_deletes=True
    )

    def __repr__(self) -> str:
        return f"<Location {self.name} ({self.type})>"
