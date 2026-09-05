"""Declarative base and the shared column mixins."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, func
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """The declarative base for every model."""


class UUIDMixin:
    """Give the table a UUID primary key."""

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )


class TimestampMixin:
    """Give the table ``created_at`` and ``updated_at``."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class SyncMixin:
    """Give the table the columns that the delta sync endpoint needs.

    ``version`` counts the edits to a row. The sync service increments it on
    every write. The mobile client compares versions to detect a conflict.

    ``deleted_at`` marks a soft delete. A hard delete cannot reach the mobile
    client, because a deleted row returns nothing to a delta query. Every
    query that returns user content must filter on ``deleted_at IS NULL``.
    """

    version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
