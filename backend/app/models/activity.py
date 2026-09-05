"""The activity log.

Every change to an item writes one line here: who did it, what changed, and
when. The log answers the questions that a bare row cannot: when did the
value change, who lent it out, and which photograph went away.

A row is never changed after it is written. That is what makes it a log.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Final

from sqlalchemy import ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, SyncMixin, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.user import User

#: The words that the ``action`` column holds. The interface groups on them.
ACTIONS: Final[tuple[str, ...]] = (
    "created",
    "changed",
    "moved",
    "photographed",
    "photo_removed",
    "thumbnail_set",
    "lent",
    "returned",
    "serviced",
    "component_fitted",
    "component_changed",
    "component_removed",
    "deleted",
)


class Activity(UUIDMixin, TimestampMixin, SyncMixin, Base):
    """One line in the log of an item."""

    __tablename__ = "activity"
    __table_args__ = (
        Index("ix_activity_entity", "entity_type", "entity_id", "created_at"),
        Index("ix_activity_user_time", "user_id", "created_at"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    #: "item" today. The column exists so that a component or a cable can
    #: keep a log without a second table.
    entity_type: Mapped[str] = mapped_column(String(20), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)

    action: Mapped[str] = mapped_column(String(30), nullable=False)
    #: One sentence for a person to read: "The value changed to $899.00."
    summary: Mapped[str] = mapped_column(String(300), nullable=False)
    #: The longer story, when there is one. The field list of a big edit.
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: The name of the person who made the change, as it was on that day.
    actor: Mapped[str | None] = mapped_column(String(150), nullable=True)

    user: Mapped[User] = relationship()

    def __repr__(self) -> str:
        return f"<Activity {self.action} {self.entity_id}>"
