"""Location schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel

LOCATION_TYPE_PATTERN = "^(room|zone|container)$"


class LocationCreate(BaseModel):
    """Create a location."""

    name: str = Field(min_length=1, max_length=200)
    type: str = Field(default="room", pattern=LOCATION_TYPE_PATTERN)
    parent_id: uuid.UUID | None = None
    description: str | None = None
    sort_order: int = 0


class LocationUpdate(BaseModel):
    """Change a location. Every field is optional."""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    type: str | None = Field(default=None, pattern=LOCATION_TYPE_PATTERN)
    parent_id: uuid.UUID | None = None
    description: str | None = None
    sort_order: int | None = None


class LocationRead(ORMModel):
    """A location, without its children."""

    id: uuid.UUID
    user_id: uuid.UUID
    parent_id: uuid.UUID | None
    name: str
    type: str
    description: str | None
    photo_path: str | None
    sort_order: int
    version: int
    created_at: datetime
    updated_at: datetime


class LocationNode(LocationRead):
    """A location with its children, for the tree endpoint."""

    children: list[LocationNode] = Field(default_factory=list)
    item_count: int = Field(
        default=0, description="Items directly in this location, not in its children."
    )


LocationNode.model_rebuild()
