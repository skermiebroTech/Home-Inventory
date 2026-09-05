"""Receipt schemas."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from datetime import date as DateOnly
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class ReceiptLineRead(ORMModel):
    """One line on a receipt."""

    id: uuid.UUID
    receipt_id: uuid.UUID
    item_id: uuid.UUID | None
    line_text: str
    line_amount: Decimal | None
    created_at: datetime


class ReceiptUpdate(BaseModel):
    """Correct the data read from a receipt."""

    vendor: str | None = Field(default=None, max_length=200)
    purchase_date: date | None = None
    total_amount: Decimal | None = Field(
        default=None, ge=0, max_digits=12, decimal_places=2
    )
    currency: str | None = Field(default=None, min_length=3, max_length=3)


class ReceiptRead(ORMModel):
    """A receipt in a list."""

    id: uuid.UUID
    user_id: uuid.UUID
    file_path: str
    thumbnail_path: str | None
    vendor: str | None
    purchase_date: date | None
    total_amount: Decimal | None
    currency: str
    version: int
    created_at: datetime
    updated_at: datetime


class ReceiptDetail(ReceiptRead):
    """One receipt with its OCR output and its lines."""

    ocr_raw_text: str | None = None
    ocr_parsed_json: dict[str, Any] | None = None
    lines: list[ReceiptLineRead] = Field(default_factory=list)


class ParsedReceiptLine(BaseModel):
    """One line as the text model returned it."""

    name: str
    quantity: Decimal | None = None
    unit_price: Decimal | None = None
    total: Decimal | None = None


class ParsedReceipt(BaseModel):
    """The structured result of a receipt parse.

    Every field may be null. The model returns null when it cannot read a
    value, and the user corrects it.
    """

    store_name: str | None = None
    # The annotation uses an alias, because the field name ``date`` would
    # otherwise shadow the ``date`` type inside this class body.
    date: DateOnly | None = None
    items: list[ParsedReceiptLine] = Field(default_factory=list)
    subtotal: Decimal | None = None
    tax: Decimal | None = None
    grand_total: Decimal | None = None
    currency: str | None = None
