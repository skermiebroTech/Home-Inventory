"""Delta sync schemas for the offline-first mobile application."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.custom_field import CustomFieldRead
from app.schemas.item import ItemPhotoRead, ItemRead
from app.schemas.location import LocationRead
from app.schemas.maintenance import MaintenanceRead
from app.schemas.receipt import ReceiptRead
from app.schemas.tag import TagRead


class SyncEntity(StrEnum):
    """The tables that the mobile application mirrors."""

    ITEM = "item"
    ITEM_PHOTO = "item_photo"
    LOCATION = "location"
    TAG = "tag"
    RECEIPT = "receipt"
    MAINTENANCE = "maintenance"
    CUSTOM_FIELD = "custom_field"


class SyncOp(StrEnum):
    """What the client did to a row while it was offline."""

    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"


class SyncChanges(BaseModel):
    """Everything that changed on the server since a timestamp.

    ``deleted`` holds the ids of soft deleted rows. A hard delete cannot
    appear in a delta query, so every user table keeps a ``deleted_at``
    tombstone instead.
    """

    since: datetime | None
    server_time: datetime = Field(
        description="Send this value back as ``since`` on the next sync."
    )
    items: list[ItemRead] = Field(default_factory=list)
    item_photos: list[ItemPhotoRead] = Field(default_factory=list)
    locations: list[LocationRead] = Field(default_factory=list)
    tags: list[TagRead] = Field(default_factory=list)
    receipts: list[ReceiptRead] = Field(default_factory=list)
    maintenance_logs: list[MaintenanceRead] = Field(default_factory=list)
    custom_fields: list[CustomFieldRead] = Field(default_factory=list)
    deleted: dict[SyncEntity, list[uuid.UUID]] = Field(default_factory=dict)
    has_more: bool = Field(
        default=False,
        description="True when the page limit cut the result. Sync again.",
    )


class SyncChange(BaseModel):
    """One change that the client made while it was offline."""

    entity: SyncEntity
    op: SyncOp
    id: uuid.UUID = Field(
        description="The client creates the UUID, so a create is repeatable."
    )
    base_version: int | None = Field(
        default=None,
        description="The version the client last saw. Used to detect a conflict.",
    )
    payload: dict[str, Any] | None = Field(
        default=None, description="The row fields. Null for a delete."
    )
    client_updated_at: datetime


class SyncPush(BaseModel):
    """A batch of offline changes."""

    changes: list[SyncChange] = Field(min_length=1, max_length=500)


class SyncConflict(BaseModel):
    """A change that the server overwrote.

    The server always wins. The client shows a message and takes the server
    value.
    """

    entity: SyncEntity
    id: uuid.UUID
    reason: str
    server_version: int


class SyncPushResult(BaseModel):
    """What the server did with a pushed batch."""

    applied: int
    rejected: int
    conflicts: list[SyncConflict] = Field(default_factory=list)
    server_time: datetime
