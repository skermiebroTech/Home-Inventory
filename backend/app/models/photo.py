"""Photographs of a component or a cable.

An item keeps its photographs in ``item_photos``, because an item photograph
also carries the OCR text and the words of the model. A component and a cable
need less: a picture, a thumbnail, and one flag that says which picture stands
for the row in a list.

One table serves both. ``owner_type`` names the table that the row belongs to,
so a third kind of owner needs no new table and no new routes.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Final

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, SyncMixin, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.user import User

#: The tables that can own a row here.
PHOTO_OWNERS: Final[tuple[str, ...]] = ("component", "cable")


class Photo(UUIDMixin, TimestampMixin, SyncMixin, Base):
    """One photograph of a component or a cable."""

    __tablename__ = "photos"
    __table_args__ = (
        Index("ix_photos_owner", "owner_type", "owner_id"),
        Index("ix_photos_user", "user_id"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    #: "component" or "cable". No foreign key can point at two tables, so the
    #: routes check that the owner exists and that this user owns it.
    owner_type: Mapped[str] = mapped_column(String(20), nullable=False)
    owner_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)

    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    thumbnail_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    #: The picture that stands for the row in a list. One for each owner.
    is_primary: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    sort_order: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    caption: Mapped[str | None] = mapped_column(String(300), nullable=True)

    user: Mapped[User] = relationship()

    def __repr__(self) -> str:
        return f"<Photo {self.owner_type} {self.file_path}>"
