"""The maintenance log model."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Date, ForeignKey, Numeric, Text
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, SyncMixin, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.item import Item


class MaintenanceLog(UUIDMixin, TimestampMixin, SyncMixin, Base):
    """A record of service work on an item, and when the next work is due."""

    __tablename__ = "maintenance_logs"

    item_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    date_performed: Mapped[date | None] = mapped_column(Date, nullable=True)
    next_due_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    cost: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    item: Mapped[Item] = relationship(back_populates="maintenance_logs")

    def __repr__(self) -> str:
        return f"<MaintenanceLog {self.description[:40]}>"
