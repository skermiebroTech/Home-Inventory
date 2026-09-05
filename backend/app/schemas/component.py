"""Component schemas: the catalogue, what is fitted, and the spares."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel

# --------------------------------------------------------------------------
# The catalogue
# --------------------------------------------------------------------------


class ComponentBase(BaseModel):
    """The fields that create and update share."""

    name: str = Field(min_length=1, max_length=200)
    brand: str | None = Field(default=None, max_length=150)
    model_number: str | None = Field(default=None, max_length=150)
    category: str | None = Field(default=None, max_length=100)
    description: str | None = None
    default_price: Decimal | None = Field(
        default=None,
        ge=0,
        max_digits=12,
        decimal_places=2,
        description="What one costs, when the fitted part names no price.",
    )
    is_consumable: bool = Field(
        default=False,
        description="A filter or a blade runs out. A gearbox does not.",
    )


class ComponentCreate(ComponentBase):
    """Add one kind of part to the catalogue."""


class ComponentUpdate(BaseModel):
    """Change a catalogue entry. Every field is optional."""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    brand: str | None = Field(default=None, max_length=150)
    model_number: str | None = Field(default=None, max_length=150)
    category: str | None = Field(default=None, max_length=100)
    description: str | None = None
    default_price: Decimal | None = Field(
        default=None, ge=0, max_digits=12, decimal_places=2
    )
    is_consumable: bool | None = None


class ComponentRead(ORMModel):
    """One catalogue entry."""

    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    brand: str | None
    model_number: str | None
    category: str | None
    description: str | None
    default_price: Decimal | None
    is_consumable: bool
    version: int
    created_at: datetime
    updated_at: datetime
    thumbnail_path: str | None = Field(
        default=None, description="The picture that stands for this component."
    )
    photo_count: int = 0


class ComponentDetail(ComponentRead):
    """One catalogue entry, with where it is used and what is on the shelf."""

    fitted_count: int = Field(
        default=0, description="How many items carry this component."
    )
    spare_quantity: int = Field(default=0, description="How many are on the shelf.")
    fitted_to: list[ComponentUse] = Field(default_factory=list)


class ComponentUse(BaseModel):
    """One item that carries this component."""

    item_id: uuid.UUID
    item_name: str
    quantity: int


# --------------------------------------------------------------------------
# Fitted to an item
# --------------------------------------------------------------------------


class ItemComponentWrite(BaseModel):
    """Fit a component to an item, or change the one that is fitted."""

    component_id: uuid.UUID
    quantity: int = Field(default=1, ge=1)
    price: Decimal | None = Field(
        default=None,
        ge=0,
        max_digits=12,
        decimal_places=2,
        description="What this one cost. Leave empty to use the default price.",
    )
    serial_number: str | None = Field(default=None, max_length=150)
    fitted_on: date | None = None
    notes: str | None = None


class ItemComponentUpdate(BaseModel):
    """Change a fitted component. Every field is optional."""

    quantity: int | None = Field(default=None, ge=1)
    price: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    serial_number: str | None = Field(default=None, max_length=150)
    fitted_on: date | None = None
    notes: str | None = None


class ItemComponentRow(ORMModel):
    """One fitted component, exactly as the table holds it.

    The sync endpoint sends this. The phone holds the catalogue too, so it
    joins the name itself.
    """

    id: uuid.UUID
    item_id: uuid.UUID
    component_id: uuid.UUID
    quantity: int
    price: Decimal | None
    serial_number: str | None
    fitted_on: date | None
    notes: str | None
    version: int
    created_at: datetime
    updated_at: datetime


class ItemComponentRead(ItemComponentRow):
    """One fitted component, with the catalogue fields joined in."""

    name: str = ""
    brand: str | None = None
    model_number: str | None = None
    is_consumable: bool = False
    default_price: Decimal | None = None
    effective_price: Decimal | None = Field(
        default=None,
        description="The price of this one, or the default when it has none.",
    )
    line_total: Decimal | None = Field(
        default=None, description="The effective price times the quantity."
    )


# --------------------------------------------------------------------------
# Spares
# --------------------------------------------------------------------------


class SpareWrite(BaseModel):
    """Put stock of a component on the shelf."""

    component_id: uuid.UUID
    quantity: int = Field(default=0, ge=0)
    minimum_quantity: int = Field(
        default=0,
        ge=0,
        description="Below this count the list asks you to buy more. Zero is off.",
    )
    location_id: uuid.UUID | None = None
    unit_price: Decimal | None = Field(
        default=None, ge=0, max_digits=12, decimal_places=2
    )
    notes: str | None = None


class SpareUpdate(BaseModel):
    """Change a spare. Every field is optional."""

    quantity: int | None = Field(default=None, ge=0)
    minimum_quantity: int | None = Field(default=None, ge=0)
    location_id: uuid.UUID | None = None
    unit_price: Decimal | None = Field(
        default=None, ge=0, max_digits=12, decimal_places=2
    )
    notes: str | None = None


class SpareRow(ORMModel):
    """One row of stock, exactly as the table holds it."""

    id: uuid.UUID
    user_id: uuid.UUID
    component_id: uuid.UUID
    location_id: uuid.UUID | None
    quantity: int
    minimum_quantity: int
    unit_price: Decimal | None
    notes: str | None
    version: int
    created_at: datetime
    updated_at: datetime


class SpareRead(SpareRow):
    """One row of stock, with the catalogue fields joined in."""

    name: str = ""
    brand: str | None = None
    model_number: str | None = None
    is_consumable: bool = False
    default_price: Decimal | None = None
    effective_price: Decimal | None = None
    stock_value: Decimal | None = Field(
        default=None, description="The effective price times the quantity."
    )
    location_name: str | None = None
    is_low: bool = Field(
        default=False, description="True when the count reached the minimum."
    )


class SpareUse(BaseModel):
    """Take stock off the shelf, or put it back."""

    count: int = Field(
        default=1,
        description="How many to take. A negative number puts stock back.",
    )
    note: str | None = None


ComponentDetail.model_rebuild()
