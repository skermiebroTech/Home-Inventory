"""Custom field schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class CustomFieldCreate(BaseModel):
    """Add a named value to an item."""

    field_name: str = Field(min_length=1, max_length=100)
    field_value: str | None = None


class CustomFieldUpdate(BaseModel):
    """Change a custom field."""

    field_name: str | None = Field(default=None, min_length=1, max_length=100)
    field_value: str | None = None


class CustomFieldRead(ORMModel):
    """A custom field."""

    id: uuid.UUID
    item_id: uuid.UUID
    field_name: str
    field_value: str | None
    version: int
    created_at: datetime
    updated_at: datetime
