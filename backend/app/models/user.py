"""The user account model."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.item import Item
    from app.models.location import Location
    from app.models.receipt import Receipt


class User(UUIDMixin, TimestampMixin, Base):
    """A person who signs in to HomeStock."""

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(
        String(320), nullable=False, unique=True, index=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(
        String(20), nullable=False, default="user", server_default="user"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )

    locations: Mapped[list[Location]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )
    items: Mapped[list[Item]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )
    receipts: Mapped[list[Receipt]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )

    def __repr__(self) -> str:
        return f"<User {self.email}>"
