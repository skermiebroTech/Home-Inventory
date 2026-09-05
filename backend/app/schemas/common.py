"""Shared schema pieces: the response envelope, errors, and pagination."""

from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class ORMModel(BaseModel):
    """A response model that reads values from a SQLAlchemy row."""

    model_config = ConfigDict(from_attributes=True)


class ErrorDetail(BaseModel):
    """The error half of the response envelope."""

    code: str = Field(description="A stable machine readable code.")
    message: str = Field(description="A message for a person to read.")
    details: dict[str, Any] | None = Field(
        default=None, description="Extra context, such as field errors."
    )


class Envelope(BaseModel, Generic[T]):
    """Every API response uses this shape.

    On success ``error`` is null. On failure ``data`` is null.
    """

    data: T | None = None
    error: ErrorDetail | None = None


class Page(BaseModel, Generic[T]):
    """One page of a list response."""

    items: list[T]
    total: int = Field(description="Total rows that match the filter.")
    page: int = Field(description="The current page number. The first page is 1.")
    per_page: int
    pages: int = Field(description="Total number of pages.")


class Message(BaseModel):
    """A plain acknowledgement, for routes that return no object."""

    message: str


def ok(data: T) -> Envelope[T]:
    """Wrap a successful result in the envelope."""
    return Envelope[T](data=data, error=None)
