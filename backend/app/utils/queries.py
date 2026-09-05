"""Shared query helpers for the route handlers.

Every helper here enforces two rules that repeat in every router: a row
belongs to the signed in user, and a soft deleted row does not exist.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Any, Final, TypeVar

from fastapi import UploadFile
from sqlalchemy import Select, func, literal, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased, selectinload

from app.models.item import Item, ItemPhoto
from app.models.location import Location
from app.models.receipt import Receipt
from app.models.user import User
from app.schemas.common import Page
from app.schemas.item import ItemDetail, ItemPhotoRead, ItemRead
from app.utils.errors import ApiError, not_found

T = TypeVar("T")

#: The largest upload that a route accepts, in bytes.
MAX_UPLOAD_BYTES: Final[int] = 25 * 1024 * 1024

IMAGE_CONTENT_TYPES: Final[frozenset[str]] = frozenset(
    {
        "image/jpeg",
        "image/jpg",
        "image/png",
        "image/webp",
        "image/heic",
        "image/heif",
        "image/gif",
        "image/bmp",
        "image/tiff",
    }
)


# --------------------------------------------------------------------------
# Pagination
# --------------------------------------------------------------------------


async def paginate(
    session: AsyncSession,
    statement: Select[Any],
    *,
    page: int,
    per_page: int,
) -> tuple[Sequence[Any], int, int]:
    """Return one page of rows, the total row count, and the page count."""
    total = await count_rows(session, statement)
    pages = max(1, -(-total // per_page))
    rows = (
        (await session.execute(statement.offset((page - 1) * per_page).limit(per_page)))
        .scalars()
        .unique()
        .all()
    )
    return rows, total, pages


async def count_rows(session: AsyncSession, statement: Select[Any]) -> int:
    """Count the rows that a select would return."""
    counter = select(func.count()).select_from(
        statement.order_by(None).options().subquery()
    )
    return int(await session.scalar(counter) or 0)


def build_page(
    items: list[T], total: int, page: int, per_page: int, pages: int
) -> Page[T]:
    """Wrap a list of rows in the shared page shape."""
    return Page[T](
        items=items, total=total, page=page, per_page=per_page, pages=pages
    )


# --------------------------------------------------------------------------
# Row lookups
# --------------------------------------------------------------------------


def live(statement: Select[Any], model: Any) -> Select[Any]:
    """Add the soft delete filter to a select."""
    return statement.where(model.deleted_at.is_(None))


async def get_item_or_404(
    session: AsyncSession,
    item_id: uuid.UUID,
    user: User,
    *,
    with_relations: bool = False,
) -> Item:
    """Return one live item of this user, or raise 404."""
    statement = select(Item).where(
        Item.id == item_id, Item.user_id == user.id, Item.deleted_at.is_(None)
    )
    if with_relations:
        statement = statement.options(
            selectinload(Item.photos), selectinload(Item.tags)
        )
    item = (await session.execute(statement)).scalars().first()
    if item is None:
        raise not_found("The item")
    return item


async def get_location_or_404(
    session: AsyncSession, location_id: uuid.UUID, user: User
) -> Location:
    """Return one live location of this user, or raise 404."""
    statement = select(Location).where(
        Location.id == location_id,
        Location.user_id == user.id,
        Location.deleted_at.is_(None),
    )
    location = (await session.execute(statement)).scalars().first()
    if location is None:
        raise not_found("The location")
    return location


async def get_receipt_or_404(
    session: AsyncSession,
    receipt_id: uuid.UUID,
    user: User,
    *,
    with_lines: bool = False,
) -> Receipt:
    """Return one live receipt of this user, or raise 404."""
    statement = select(Receipt).where(
        Receipt.id == receipt_id,
        Receipt.user_id == user.id,
        Receipt.deleted_at.is_(None),
    )
    if with_lines:
        statement = statement.options(selectinload(Receipt.lines))
    receipt = (await session.execute(statement)).scalars().first()
    if receipt is None:
        raise not_found("The receipt")
    return receipt


# --------------------------------------------------------------------------
# The location tree
# --------------------------------------------------------------------------


async def descendant_location_ids(
    session: AsyncSession, root_id: uuid.UUID, user_id: uuid.UUID
) -> list[uuid.UUID]:
    """Return the root location and every location below it.

    `GET /api/items?location_id=...&include_sublocations=true` uses this, so
    that a request for a room also returns the items in its containers.
    """
    anchor = (
        select(Location.id)
        .where(
            Location.id == root_id,
            Location.user_id == user_id,
            Location.deleted_at.is_(None),
        )
        .cte("location_tree", recursive=True)
    )
    child = aliased(Location)
    tree = anchor.union_all(
        select(child.id).where(
            child.parent_id == anchor.c.id, child.deleted_at.is_(None)
        )
    )
    rows = await session.execute(select(tree.c.id))
    return [row[0] for row in rows]


async def location_path_names(
    session: AsyncSession, location_id: uuid.UUID | None
) -> list[str]:
    """Return the location names from the root down, for a breadcrumb."""
    if location_id is None:
        return []
    anchor = (
        select(
            Location.id,
            Location.parent_id,
            Location.name,
            literal(0).label("depth"),
        )
        .where(Location.id == location_id)
        .cte("location_path", recursive=True)
    )
    parent = aliased(Location)
    walk = anchor.union_all(
        select(
            parent.id,
            parent.parent_id,
            parent.name,
            anchor.c.depth + 1,
        ).where(parent.id == anchor.c.parent_id)
    )
    rows = await session.execute(
        select(walk.c.name).order_by(walk.c.depth.desc())
    )
    return [row[0] for row in rows]


async def would_create_cycle(
    session: AsyncSession,
    location_id: uuid.UUID,
    new_parent_id: uuid.UUID,
    user_id: uuid.UUID,
) -> bool:
    """Return True if moving a location under `new_parent_id` makes a loop."""
    if location_id == new_parent_id:
        return True
    descendants = await descendant_location_ids(session, location_id, user_id)
    return new_parent_id in descendants


# --------------------------------------------------------------------------
# Response builders
# --------------------------------------------------------------------------


def pick_primary_photo(item: Item) -> ItemPhoto | None:
    """Return the photo to show in a list view."""
    photos = list(item.photos or [])
    if not photos:
        return None
    for photo in photos:
        if photo.is_primary:
            return photo
    return photos[0]


def to_item_read(item: Item) -> ItemRead:
    """Build the list shape of one item."""
    read = ItemRead.model_validate(item)
    primary = pick_primary_photo(item)
    if primary is not None:
        read.primary_photo = ItemPhotoRead.model_validate(primary)
    return read


async def to_item_detail(session: AsyncSession, item: Item) -> ItemDetail:
    """Build the full shape of one item, with its photos and its breadcrumb."""
    detail = ItemDetail.model_validate(item)
    primary = pick_primary_photo(item)
    if primary is not None:
        detail.primary_photo = ItemPhotoRead.model_validate(primary)
    detail.location_path = await location_path_names(session, item.location_id)
    return detail


# --------------------------------------------------------------------------
# Uploads
# --------------------------------------------------------------------------


async def read_upload(
    file: UploadFile, *, max_bytes: int = MAX_UPLOAD_BYTES, images_only: bool = True
) -> bytes:
    """Read one uploaded file into memory, with a size and a type check."""
    if images_only and file.content_type:
        if file.content_type.split(";")[0].strip().lower() not in IMAGE_CONTENT_TYPES:
            raise ApiError(
                415,
                "unsupported_media_type",
                f"{file.content_type} is not an image that this server accepts.",
            )
    data = await file.read()
    if not data:
        raise ApiError(400, "empty_upload", "The uploaded file is empty.")
    if len(data) > max_bytes:
        raise ApiError(
            413,
            "upload_too_large",
            f"The file is larger than {max_bytes // (1024 * 1024)} MB.",
        )
    return data


__all__ = [
    "IMAGE_CONTENT_TYPES",
    "MAX_UPLOAD_BYTES",
    "build_page",
    "count_rows",
    "descendant_location_ids",
    "get_item_or_404",
    "get_location_or_404",
    "get_receipt_or_404",
    "live",
    "location_path_names",
    "paginate",
    "pick_primary_photo",
    "read_upload",
    "to_item_detail",
    "to_item_read",
    "would_create_cycle",
]
