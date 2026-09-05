"""Location routes."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, status
from sqlalchemy import func, select

from app.models.item import Item
from app.models.location import Location
from app.models.user import User
from app.schemas.common import Envelope, Message, ok
from app.schemas.location import (
    LocationCreate,
    LocationNode,
    LocationRead,
    LocationUpdate,
)
from app.utils.auth import CurrentUser, SessionDep
from app.utils.errors import ApiError, not_found
from app.utils.queries import (
    descendant_location_ids,
    get_location_or_404,
    would_create_cycle,
)

router = APIRouter(prefix="/api/locations", tags=["Locations"])


async def _item_counts(session: SessionDep, user: User) -> dict[uuid.UUID, int]:
    """Count the items that sit directly in each location."""
    rows = await session.execute(
        select(Item.location_id, func.count(Item.id))
        .where(
            Item.user_id == user.id,
            Item.deleted_at.is_(None),
            Item.location_id.is_not(None),
        )
        .group_by(Item.location_id)
    )
    return {row[0]: int(row[1]) for row in rows}


async def _assert_parent(
    session: SessionDep, parent_id: uuid.UUID | None, user: User
) -> None:
    """Raise 404 if the parent location is not a live location of this user."""
    if parent_id is None:
        return
    await get_location_or_404(session, parent_id, user)


@router.get(
    "",
    response_model=Envelope[list[LocationNode]],
    summary="Return the whole location tree.",
)
async def list_locations(
    user: CurrentUser, session: SessionDep
) -> Envelope[list[LocationNode]]:
    rows = (
        (
            await session.execute(
                select(Location)
                .where(Location.user_id == user.id, Location.deleted_at.is_(None))
                .order_by(Location.sort_order, Location.name)
            )
        )
        .scalars()
        .all()
    )
    counts = await _item_counts(session, user)

    nodes: dict[uuid.UUID, LocationNode] = {}
    for row in rows:
        # The node is built from the flat shape. Reading `row.children` here
        # would make the ORM load the whole subtree, one query at a time.
        flat = LocationRead.model_validate(row)
        nodes[row.id] = LocationNode(
            **flat.model_dump(), children=[], item_count=counts.get(row.id, 0)
        )

    roots: list[LocationNode] = []
    for row in rows:
        node = nodes[row.id]
        parent = nodes.get(row.parent_id) if row.parent_id else None
        if parent is None:
            # A location whose parent is deleted becomes a root, so that it
            # never disappears from the tree.
            roots.append(node)
        else:
            parent.children.append(node)
    return ok(roots)


@router.post(
    "",
    response_model=Envelope[LocationRead],
    status_code=status.HTTP_201_CREATED,
    summary="Create a location.",
)
async def create_location(
    body: LocationCreate, user: CurrentUser, session: SessionDep
) -> Envelope[LocationRead]:
    await _assert_parent(session, body.parent_id, user)

    location = Location(
        user_id=user.id,
        parent_id=body.parent_id,
        name=body.name.strip(),
        type=body.type,
        description=body.description,
        sort_order=body.sort_order,
    )
    session.add(location)
    await session.commit()
    await session.refresh(location)
    return ok(LocationRead.model_validate(location))


@router.get(
    "/{location_id}",
    response_model=Envelope[LocationRead],
    summary="Return one location.",
)
async def get_location(
    location_id: uuid.UUID, user: CurrentUser, session: SessionDep
) -> Envelope[LocationRead]:
    location = await get_location_or_404(session, location_id, user)
    return ok(LocationRead.model_validate(location))


@router.put(
    "/{location_id}",
    response_model=Envelope[LocationRead],
    summary="Change a location. Set parent_id to move it.",
)
async def update_location(
    location_id: uuid.UUID,
    body: LocationUpdate,
    user: CurrentUser,
    session: SessionDep,
) -> Envelope[LocationRead]:
    location = await get_location_or_404(session, location_id, user)
    changes = body.model_dump(exclude_unset=True)

    if "parent_id" in changes:
        new_parent = changes["parent_id"]
        if new_parent is not None:
            await _assert_parent(session, new_parent, user)
            if await would_create_cycle(session, location_id, new_parent, user.id):
                raise ApiError(
                    status.HTTP_409_CONFLICT,
                    "invalid_move",
                    "A location cannot move inside itself or inside its own "
                    "child location.",
                )

    for field, value in changes.items():
        setattr(location, field, value.strip() if field == "name" else value)
    location.version += 1

    await session.commit()
    await session.refresh(location)
    return ok(LocationRead.model_validate(location))


@router.delete(
    "/{location_id}",
    response_model=Envelope[Message],
    summary="Delete a location and its child locations.",
    description=(
        "The items inside keep existing. Their location_id becomes null, and "
        "the user files them again."
    ),
)
async def delete_location(
    location_id: uuid.UUID, user: CurrentUser, session: SessionDep
) -> Envelope[Message]:
    await get_location_or_404(session, location_id, user)
    doomed = await descendant_location_ids(session, location_id, user.id)
    if not doomed:
        raise not_found("The location")

    moment = datetime.now(UTC)
    rows = (
        (
            await session.execute(
                select(Location).where(
                    Location.id.in_(doomed), Location.deleted_at.is_(None)
                )
            )
        )
        .scalars()
        .all()
    )
    for row in rows:
        # A soft delete, so that the mobile application learns about it on the
        # next sync. A hard delete would never reach the client.
        row.deleted_at = moment
        row.version += 1

    orphans = (
        (
            await session.execute(
                select(Item).where(
                    Item.user_id == user.id,
                    Item.location_id.in_(doomed),
                    Item.deleted_at.is_(None),
                )
            )
        )
        .scalars()
        .all()
    )
    for item in orphans:
        item.location_id = None
        item.version += 1

    await session.commit()
    return ok(
        Message(
            message=(
                f"The location and {len(rows) - 1} child locations are deleted. "
                f"{len(orphans)} items are now unplaced."
            )
        )
    )
