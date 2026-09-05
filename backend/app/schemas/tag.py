"""Tag schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel

HEX_COLOR_PATTERN = "^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$"


class TagCreate(BaseModel):
    """Create a tag."""

    name: str = Field(min_length=1, max_length=80)
    color: str = Field(default="#64748b", pattern=HEX_COLOR_PATTERN)


class TagUpdate(BaseModel):
    """Change a tag. Every field is optional."""

    name: str | None = Field(default=None, min_length=1, max_length=80)
    color: str | None = Field(default=None, pattern=HEX_COLOR_PATTERN)


class TagRead(ORMModel):
    """A tag."""

    id: uuid.UUID
    name: str
    color: str
    created_at: datetime
    updated_at: datetime
