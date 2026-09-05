"""Cable schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class CableBase(BaseModel):
    """The fields that create and update share."""

    name: str = Field(min_length=1, max_length=200)
    kind: str | None = Field(
        default=None,
        max_length=100,
        description='The family: "USB", "HDMI", "Ethernet", or "Power".',
    )
    connector_a: str | None = Field(default=None, max_length=80)
    connector_b: str | None = Field(default=None, max_length=80)
    length_cm: int | None = Field(
        default=None, ge=0, le=100_000, description="The length in centimetres."
    )
    colour: str | None = Field(default=None, max_length=50)
    brand: str | None = Field(default=None, max_length=150)
    specification: str | None = Field(
        default=None,
        max_length=200,
        description='What it can do: "USB 3.2, 10 Gbps, 100 W" or "Cat6a".',
    )
    quantity: int = Field(default=1, ge=0)
    price: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    notes: str | None = None
    location_id: uuid.UUID | None = None
    item_id: uuid.UUID | None = Field(
        default=None, description="The device that this lead came with."
    )


class CableCreate(CableBase):
    """Add one cable."""


class CableUpdate(BaseModel):
    """Change a cable. Every field is optional."""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    kind: str | None = Field(default=None, max_length=100)
    connector_a: str | None = Field(default=None, max_length=80)
    connector_b: str | None = Field(default=None, max_length=80)
    length_cm: int | None = Field(default=None, ge=0, le=100_000)
    colour: str | None = Field(default=None, max_length=50)
    brand: str | None = Field(default=None, max_length=150)
    specification: str | None = Field(default=None, max_length=200)
    quantity: int | None = Field(default=None, ge=0)
    price: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    notes: str | None = None
    location_id: uuid.UUID | None = None
    item_id: uuid.UUID | None = None


class CableRow(ORMModel):
    """One cable, exactly as the table holds it. The phone reads this."""

    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    kind: str | None
    connector_a: str | None
    connector_b: str | None
    length_cm: int | None
    colour: str | None
    brand: str | None
    specification: str | None
    quantity: int
    price: Decimal | None
    notes: str | None
    location_id: uuid.UUID | None
    item_id: uuid.UUID | None
    version: int
    created_at: datetime
    updated_at: datetime


class CableRead(CableRow):
    """One cable, with the words that the interface shows."""

    ends: str | None = Field(default=None, description='Such as "USB-C to HDMI".')
    length_label: str | None = Field(default=None, description='Such as "2 m".')
    total_value: Decimal | None = Field(
        default=None, description="The price of one, times the count."
    )
    location_name: str | None = None
    item_name: str | None = None
    thumbnail_path: str | None = Field(
        default=None, description="The picture that stands for this cable."
    )
    photo_count: int = 0
