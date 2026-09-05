"""Receipts and the lines that link a receipt to inventory items."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import Date, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, SyncMixin, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.item import Item
    from app.models.user import User


class Receipt(UUIDMixin, TimestampMixin, SyncMixin, Base):
    """A photographed receipt and the data read from it."""

    __tablename__ = "receipts"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    thumbnail_path: Mapped[str | None] = mapped_column(String(500), nullable=True)

    vendor: Mapped[str | None] = mapped_column(String(200), nullable=True, index=True)
    purchase_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    total_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    currency: Mapped[str] = mapped_column(
        String(3), nullable=False, default="AUD", server_default="AUD"
    )

    # Raw Tesseract output. Kept so a parse can be repeated without the image.
    ocr_raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    # The structured result from the text model.
    ocr_parsed_json: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB, nullable=True
    )

    user: Mapped[User] = relationship(back_populates="receipts")
    lines: Mapped[list[ReceiptItem]] = relationship(
        back_populates="receipt", cascade="all, delete-orphan", passive_deletes=True
    )

    def __repr__(self) -> str:
        return f"<Receipt {self.vendor} {self.purchase_date}>"


class ReceiptItem(UUIDMixin, TimestampMixin, Base):
    """One line on a receipt. It may point at an inventory item."""

    __tablename__ = "receipt_items"

    receipt_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("receipts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # A deleted item must not delete the receipt line. The line stays as a
    # record of the purchase.
    item_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("items.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    line_text: Mapped[str] = mapped_column(String(500), nullable=False)
    line_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)

    receipt: Mapped[Receipt] = relationship(back_populates="lines")
    item: Mapped[Item | None] = relationship(back_populates="receipt_items")

    def __repr__(self) -> str:
        return f"<ReceiptItem {self.line_text}>"
