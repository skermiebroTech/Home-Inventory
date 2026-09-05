"""Item and item photo schemas."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel
from app.schemas.tag import TagRead

CONDITION_PATTERN = "^(new|good|fair|poor)$"


class ItemPhotoRead(ORMModel):
    """One photograph of an item."""

    id: uuid.UUID
    item_id: uuid.UUID
    file_path: str
    thumbnail_path: str | None
    is_primary: bool
    ai_description: str | None
    ocr_text: str | None = Field(
        default=None,
        description="The text that OCR read from the photograph, if any.",
    )
    created_at: datetime


class ItemBase(BaseModel):
    """The fields shared by create and update."""

    name: str = Field(min_length=1, max_length=300)
    description: str | None = None
    location_id: uuid.UUID | None = None
    category: str | None = Field(default=None, max_length=100)
    subcategory: str | None = Field(default=None, max_length=100)
    brand: str | None = Field(default=None, max_length=150)
    model: str | None = Field(default=None, max_length=150)
    serial_number: str | None = Field(default=None, max_length=150)
    barcode: str | None = Field(default=None, max_length=64)
    purchase_price: Decimal | None = Field(
        default=None, ge=0, max_digits=12, decimal_places=2
    )
    current_value: Decimal | None = Field(
        default=None, ge=0, max_digits=12, decimal_places=2
    )
    purchase_date: date | None = None
    purchase_location: str | None = Field(default=None, max_length=200)
    warranty_expires: date | None = None
    condition: str | None = Field(default=None, pattern=CONDITION_PATTERN)
    quantity: int = Field(default=1, ge=0)
    notes: str | None = None
    owner: str | None = Field(
        default=None,
        max_length=150,
        description="The person in the house who owns this item.",
    )


class ItemCreate(ItemBase):
    """Create an item."""

    tag_ids: list[uuid.UUID] = Field(default_factory=list)


class ItemUpdate(BaseModel):
    """Change an item. Every field is optional."""

    name: str | None = Field(default=None, min_length=1, max_length=300)
    description: str | None = None
    location_id: uuid.UUID | None = None
    category: str | None = Field(default=None, max_length=100)
    subcategory: str | None = Field(default=None, max_length=100)
    brand: str | None = Field(default=None, max_length=150)
    model: str | None = Field(default=None, max_length=150)
    serial_number: str | None = Field(default=None, max_length=150)
    barcode: str | None = Field(default=None, max_length=64)
    purchase_price: Decimal | None = Field(
        default=None, ge=0, max_digits=12, decimal_places=2
    )
    current_value: Decimal | None = Field(
        default=None, ge=0, max_digits=12, decimal_places=2
    )
    purchase_date: date | None = None
    purchase_location: str | None = Field(default=None, max_length=200)
    warranty_expires: date | None = None
    condition: str | None = Field(default=None, pattern=CONDITION_PATTERN)
    quantity: int | None = Field(default=None, ge=0)
    notes: str | None = None
    owner: str | None = Field(default=None, max_length=150)
    tag_ids: list[uuid.UUID] | None = None


class ItemRead(ORMModel):
    """An item in a list. It carries no nested collections except tags."""

    id: uuid.UUID
    user_id: uuid.UUID
    location_id: uuid.UUID | None
    name: str
    description: str | None
    category: str | None
    subcategory: str | None
    brand: str | None
    model: str | None
    serial_number: str | None
    barcode: str | None
    purchase_price: Decimal | None
    current_value: Decimal | None
    purchase_date: date | None
    purchase_location: str | None
    warranty_expires: date | None
    condition: str | None
    quantity: int
    notes: str | None
    owner: str | None = None
    is_lent: bool
    lent_to: str | None
    lent_date: date | None
    version: int
    created_at: datetime
    updated_at: datetime

    tags: list[TagRead] = Field(default_factory=list)
    primary_photo: ItemPhotoRead | None = None


class ItemDetail(ItemRead):
    """One item with everything attached to it."""

    photos: list[ItemPhotoRead] = Field(default_factory=list)
    location_path: list[str] = Field(
        default_factory=list,
        description="The location names from the root down, for a breadcrumb.",
    )


class ItemBulkCreate(BaseModel):
    """Create many items at once, after an AI scan."""

    items: list[ItemCreate] = Field(min_length=1, max_length=100)


class ItemFilter(BaseModel):
    """The query parameters that GET /api/items accepts."""

    q: str | None = Field(default=None, description="Full text search terms.")
    location_id: uuid.UUID | None = None
    include_sublocations: bool = True
    category: str | None = None
    tag_ids: list[uuid.UUID] | None = None
    is_lent: bool | None = None
    condition: str | None = Field(default=None, pattern=CONDITION_PATTERN)
    owner: str | None = Field(default=None, max_length=150)
    min_value: Decimal | None = Field(default=None, ge=0)
    max_value: Decimal | None = Field(default=None, ge=0)
    warranty_expiring_days: int | None = Field(
        default=None, ge=0, description="Only items whose warranty ends within N days."
    )
    sort: str = Field(default="-created_at", description="Prefix with - to reverse.")
    page: int = Field(default=1, ge=1)
    per_page: int = Field(default=50, ge=1, le=200)


class LendRequest(BaseModel):
    """Lend an item to a person."""

    lent_to: str = Field(min_length=1, max_length=200)
    lent_date: date | None = None
    notes: str | None = None
