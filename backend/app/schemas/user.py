"""User schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.schemas.common import ORMModel


class UserCreate(BaseModel):
    """Create a user."""

    email: EmailStr
    name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=8, max_length=128)
    role: str = Field(default="user", pattern="^(admin|user)$")


class UserUpdate(BaseModel):
    """Change a user. Every field is optional."""

    email: EmailStr | None = None
    name: str | None = Field(default=None, min_length=1, max_length=120)
    password: str | None = Field(default=None, min_length=8, max_length=128)
    role: str | None = Field(default=None, pattern="^(admin|user)$")
    is_active: bool | None = None


class UserRead(ORMModel):
    """A user, as the API returns it. The password hash never appears here."""

    id: uuid.UUID
    email: EmailStr
    name: str
    role: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
