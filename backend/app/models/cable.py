"""Cables: the drawer of leads that every house has.

A cable is not a component and it is not an item. It has no serial number and
nobody services it. What you ask about a cable is always the same: what is on
each end, how long is it, how many do I have, and where are they? This table
answers those four questions.

A cable can also belong to an item, because the lead of a printer is the lead
of that printer. That link is optional, and the cable stays when the item
goes.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, SyncMixin, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.item import Item
    from app.models.location import Location
    from app.models.user import User


class Cable(UUIDMixin, TimestampMixin, SyncMixin, Base):
    """One kind of cable, and how many of it you hold."""

    __tablename__ = "cables"
    __table_args__ = (
        Index("ix_cables_user_kind", "user_id", "kind"),
        Index("ix_cables_user_name", "user_id", "name"),
        CheckConstraint("quantity >= 0", name="ck_cables_quantity"),
        CheckConstraint("length_cm IS NULL OR length_cm >= 0", name="ck_cables_length"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    #: The family: "USB", "HDMI", "Ethernet", "Power". The cables page groups
    #: on this, because that is how a drawer of leads sorts itself.
    kind: Mapped[str | None] = mapped_column(String(100), nullable=True)

    #: The two ends. A search matches either one, because you look for "a
    #: cable with USB-C on it" and not for a direction.
    connector_a: Mapped[str | None] = mapped_column(String(80), nullable=True)
    connector_b: Mapped[str | None] = mapped_column(String(80), nullable=True)

    #: The length in centimetres. Centimetres keep short leads honest, and
    #: the interface writes metres when the number is large.
    length_cm: Mapped[int | None] = mapped_column(Integer, nullable=True)

    colour: Mapped[str | None] = mapped_column(String(50), nullable=True)
    brand: Mapped[str | None] = mapped_column(String(150), nullable=True)
    #: What the cable can do: "USB 3.2, 10 Gbps, 100 W" or "Cat6a".
    specification: Mapped[str | None] = mapped_column(String(200), nullable=True)

    quantity: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    #: What one cost.
    price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    #: The drawer, the box, or the room that holds them.
    location_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("locations.id", ondelete="SET NULL"),
        nullable=True,
    )
    #: The device that this lead came with, if it came with one.
    item_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("items.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    user: Mapped[User] = relationship()
    location: Mapped[Location | None] = relationship()
    item: Mapped[Item | None] = relationship()

    @property
    def length_label(self) -> str | None:
        """Return the length as a person writes it: "80 cm" or "2 m"."""
        if self.length_cm is None:
            return None
        if self.length_cm < 100:
            return f"{self.length_cm} cm"
        metres = self.length_cm / 100
        return f"{metres:.2f}".rstrip("0").rstrip(".") + " m"

    @property
    def ends(self) -> str | None:
        """Return the two ends as one phrase, such as "USB-C to HDMI"."""
        if self.connector_a and self.connector_b:
            return f"{self.connector_a} to {self.connector_b}"
        return self.connector_a or self.connector_b

    def __repr__(self) -> str:
        return f"<Cable {self.name}>"
