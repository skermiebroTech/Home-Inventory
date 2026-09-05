"""NFC tag registration."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.item import Item
    from app.models.location import Location


class NfcTag(UUIDMixin, TimestampMixin, Base):
    """A physical NFC tag bound to one item or to one location."""

    __tablename__ = "nfc_tags"
    __table_args__ = (
        CheckConstraint(
            "(item_id IS NOT NULL AND location_id IS NULL)"
            " OR (item_id IS NULL AND location_id IS NOT NULL)",
            name="ck_nfc_tags_one_target",
        ),
    )

    item_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("items.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    location_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("locations.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    nfc_uid: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, index=True
    )
    label: Mapped[str | None] = mapped_column(String(200), nullable=True)

    item: Mapped[Item | None] = relationship(back_populates="nfc_tags")
    location: Mapped[Location | None] = relationship(back_populates="nfc_tags")

    def __repr__(self) -> str:
        return f"<NfcTag {self.nfc_uid}>"
