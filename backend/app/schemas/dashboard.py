"""Dashboard summary schemas."""

from __future__ import annotations

import uuid
from decimal import Decimal

from pydantic import BaseModel, Field


class LocationCount(BaseModel):
    """How many items sit in one location."""

    location_id: uuid.UUID
    location_name: str
    item_count: int
    total_value: Decimal


class DashboardSummary(BaseModel):
    """The numbers on the dashboard page."""

    total_items: int
    total_quantity: int
    total_value: Decimal
    items_by_location: list[LocationCount] = Field(default_factory=list)
    lent_count: int
    maintenance_due_count: int = Field(description="Due in the next 30 days.")
    warranty_expiring_count: int = Field(description="Ends in the next 30 days.")
    receipt_count: int
