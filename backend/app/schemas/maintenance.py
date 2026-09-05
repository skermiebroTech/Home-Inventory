"""Maintenance log schemas."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class MaintenanceCreate(BaseModel):
    """Record service work on an item."""

    description: str = Field(min_length=1)
    date_performed: date | None = None
    next_due_date: date | None = None
    cost: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    notes: str | None = None


class MaintenanceUpdate(BaseModel):
    """Change a maintenance record. Every field is optional."""

    description: str | None = Field(default=None, min_length=1)
    date_performed: date | None = None
    next_due_date: date | None = None
    cost: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    notes: str | None = None


class MaintenanceRead(ORMModel):
    """A maintenance record."""

    id: uuid.UUID
    item_id: uuid.UUID
    description: str
    date_performed: date | None
    next_due_date: date | None
    cost: Decimal | None
    notes: str | None
    version: int
    created_at: datetime
    updated_at: datetime


class MaintenanceDue(MaintenanceRead):
    """A maintenance record that is due soon."""

    item_name: str
    days_until_due: int = Field(
        description="Negative when the work is already overdue."
    )
