"""Barcode lookup schemas."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field


class BarcodeProduct(BaseModel):
    """A product found in a public barcode database."""

    barcode: str
    name: str | None = None
    brand: str | None = None
    category: str | None = None
    description: str | None = None
    image_url: str | None = None
    estimated_value_aud: Decimal | None = None
    source: str = Field(description="openfoodfacts or upcitemdb.")
