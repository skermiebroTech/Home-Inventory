"""NFC tag schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Self

from pydantic import BaseModel, Field, model_validator

from app.schemas.common import ORMModel


class NfcRegister(BaseModel):
    """Bind an NFC tag to one item or to one location.

    Give exactly one of ``item_id`` or ``location_id``.
    """

    nfc_uid: str = Field(min_length=1, max_length=64)
    item_id: uuid.UUID | None = None
    location_id: uuid.UUID | None = None
    label: str | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def _exactly_one_target(self) -> Self:
        if (self.item_id is None) == (self.location_id is None):
            raise ValueError("Give exactly one of item_id or location_id.")
        return self


class NfcRead(ORMModel):
    """A registered NFC tag."""

    id: uuid.UUID
    nfc_uid: str
    item_id: uuid.UUID | None
    location_id: uuid.UUID | None
    label: str | None
    created_at: datetime
    updated_at: datetime


class NfcLookup(BaseModel):
    """What a scanned NFC tag points at."""

    nfc_uid: str
    target_type: str = Field(description="Either item or location.")
    target_id: uuid.UUID
    target_name: str
