"""Schemas for the photographs of a component or a cable."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class PhotoRow(ORMModel):
    """One photograph, exactly as the table holds it. The phone reads this."""

    id: uuid.UUID
    user_id: uuid.UUID
    owner_type: str
    owner_id: uuid.UUID
    file_path: str
    thumbnail_path: str | None
    is_primary: bool
    sort_order: int
    caption: str | None
    version: int
    created_at: datetime
    updated_at: datetime


class PhotoUpdate(BaseModel):
    """Change one photograph."""

    caption: str | None = Field(default=None, max_length=300)
    sort_order: int | None = Field(default=None, ge=0)
