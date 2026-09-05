"""Schemas for the activity log."""

from __future__ import annotations

import uuid
from datetime import datetime

from app.schemas.common import ORMModel


class ActivityRow(ORMModel):
    """One line of the log."""

    id: uuid.UUID
    user_id: uuid.UUID
    entity_type: str
    entity_id: uuid.UUID
    action: str
    summary: str
    detail: str | None
    actor: str | None
    version: int
    created_at: datetime
    updated_at: datetime
