"""SQLAlchemy models.

Import every model here. Alembic reads ``Base.metadata`` and only sees the
tables whose modules were imported.
"""

from app.models.base import Base, SyncMixin, TimestampMixin, UUIDMixin
from app.models.cable import Cable
from app.models.component import Component, ComponentSpare, ItemComponent
from app.models.custom_field import CustomField
from app.models.item import (
    ITEM_CONDITIONS,
    Item,
    ItemPhoto,
)
from app.models.location import LOCATION_TYPES, Location
from app.models.maintenance import MaintenanceLog
from app.models.nfc import NfcTag
from app.models.receipt import Receipt, ReceiptItem
from app.models.tag import Tag, item_tags
from app.models.user import User

__all__ = [
    "ITEM_CONDITIONS",
    "LOCATION_TYPES",
    "Base",
    "Cable",
    "Component",
    "ComponentSpare",
    "CustomField",
    "Item",
    "ItemComponent",
    "ItemPhoto",
    "Location",
    "MaintenanceLog",
    "NfcTag",
    "Receipt",
    "ReceiptItem",
    "SyncMixin",
    "Tag",
    "TimestampMixin",
    "UUIDMixin",
    "User",
    "item_tags",
]
