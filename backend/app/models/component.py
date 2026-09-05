"""Components: the catalogue, what is fitted to an item, and the spares.

Three tables, because a component is three different things at once.

``components`` is the catalogue: what a part *is*. A DeWalt DCB184 battery
has one row here, whatever it is fitted to and however many you hold. It
carries the default price.

``item_components`` is one part fitted to one item. It may carry its own
price, because the same battery costs a different amount every year, and it
carries the serial number of that physical unit and the notes about it.

``component_spares`` is stock on the shelf: parts and consumables that no item
uses yet. A count, a place, and a level that asks you to buy more.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, SyncMixin, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.item import Item
    from app.models.location import Location
    from app.models.user import User


class Component(UUIDMixin, TimestampMixin, SyncMixin, Base):
    """One kind of part, in the catalogue."""

    __tablename__ = "components"
    __table_args__ = (
        Index("ix_components_user_name", "user_id", "name"),
        Index("ix_components_user_category", "user_id", "category"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    brand: Mapped[str | None] = mapped_column(String(150), nullable=True)
    model_number: Mapped[str | None] = mapped_column(
        String(150), nullable=True, index=True
    )
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    #: What one costs, when the fitted part names no price of its own.
    default_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)

    #: A filter, a blade, or an oil runs out. A gearbox does not. The spares
    #: page sorts on this, because a consumable is what you run short of.
    is_consumable: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false", index=True
    )

    user: Mapped[User] = relationship()
    fitted: Mapped[list[ItemComponent]] = relationship(
        back_populates="component", passive_deletes=True
    )
    spares: Mapped[list[ComponentSpare]] = relationship(
        back_populates="component", cascade="all, delete-orphan", passive_deletes=True
    )

    def __repr__(self) -> str:
        return f"<Component {self.name}>"


class ItemComponent(UUIDMixin, TimestampMixin, SyncMixin, Base):
    """One component fitted to one item."""

    __tablename__ = "item_components"
    __table_args__ = (
        Index("ix_item_components_item", "item_id"),
        CheckConstraint("quantity > 0", name="ck_item_components_quantity"),
    )

    item_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("items.id", ondelete="CASCADE"),
        nullable=False,
    )
    # A catalogue entry that something uses cannot be deleted. The route says
    # so, and this constraint holds the line if it ever slips through.
    component_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("components.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    quantity: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    #: What this one cost. Null means the default price of the catalogue.
    price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    serial_number: Mapped[str | None] = mapped_column(String(150), nullable=True)
    fitted_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    item: Mapped[Item] = relationship(back_populates="components")
    component: Mapped[Component] = relationship(back_populates="fitted")

    def __repr__(self) -> str:
        return f"<ItemComponent {self.component_id} on {self.item_id}>"


class ComponentSpare(UUIDMixin, TimestampMixin, SyncMixin, Base):
    """Stock of one component that no item uses yet."""

    __tablename__ = "component_spares"
    __table_args__ = (
        # One row for each component in each place. Two rows for the same
        # shelf would only make the count wrong.
        UniqueConstraint(
            "component_id", "location_id", name="uq_spares_component_location"
        ),
        CheckConstraint("quantity >= 0", name="ck_spares_quantity"),
        Index("ix_spares_user", "user_id"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    component_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("components.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # A spare that sits in a box knows which box. A deleted box leaves the
    # spare where it is, without a place.
    location_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("locations.id", ondelete="SET NULL"),
        nullable=True,
    )

    quantity: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    #: Below this count, the spares page asks you to buy more. Zero turns the
    #: warning off.
    minimum_quantity: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    #: What one of these cost you. Null means the default price.
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    user: Mapped[User] = relationship()
    component: Mapped[Component] = relationship(back_populates="spares")
    location: Mapped[Location | None] = relationship()

    @property
    def is_low(self) -> bool:
        """Return True when the stock has fallen to the level you set."""
        return self.minimum_quantity > 0 and self.quantity <= self.minimum_quantity

    def __repr__(self) -> str:
        return f"<ComponentSpare {self.component_id} x{self.quantity}>"
