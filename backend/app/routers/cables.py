"""Cable routes: the drawer of leads."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Query, status
from sqlalchemy import func, or_, select

from app.models.cable import Cable
from app.models.item import Item
from app.models.location import Location
from app.models.user import User
from app.schemas.cable import CableCreate, CableRead, CableUpdate
from app.schemas.common import Envelope, Message, ok
from app.utils.auth import CurrentUser, SessionDep
from app.utils.errors import not_found
from app.utils.queries import get_item_or_404, get_location_or_404

router = APIRouter(prefix="/api/cables", tags=["Cables"])


async def _get_cable_or_404(
    session: SessionDep, cable_id: uuid.UUID, user: User
) -> Cable:
    """Return one live cable of this user, or raise 404."""
    cable = (
        await session.execute(
            select(Cable).where(
                Cable.id == cable_id,
                Cable.user_id == user.id,
                Cable.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if cable is None:
        raise not_found("The cable")
    return cable


async def _names(session: SessionDep, user: User) -> tuple[dict, dict]:
    """Return the name of every location and every item, by id."""
    places = await session.execute(
        select(Location.id, Location.name).where(Location.user_id == user.id)
    )
    items = await session.execute(
        select(Item.id, Item.name).where(
            Item.user_id == user.id, Item.deleted_at.is_(None)
        )
    )
    return {row[0]: row[1] for row in places}, {row[0]: row[1] for row in items}


def _read(cable: Cable, places: dict, items: dict) -> CableRead:
    """Build the reply for one cable."""
    read = CableRead.model_validate(cable)
    read.ends = cable.ends
    read.length_label = cable.length_label
    read.total_value = cable.price * cable.quantity if cable.price is not None else None
    read.location_name = places.get(cable.location_id) if cable.location_id else None
    read.item_name = items.get(cable.item_id) if cable.item_id else None
    return read


async def _check_links(
    session: SessionDep,
    user: User,
    location_id: uuid.UUID | None,
    item_id: uuid.UUID | None,
) -> None:
    """Refuse a place or a device that this user does not have."""
    if location_id is not None:
        await get_location_or_404(session, location_id, user)
    if item_id is not None:
        await get_item_or_404(session, item_id, user)


@router.get(
    "",
    response_model=Envelope[list[CableRead]],
    summary="List the cables.",
    description=(
        "``connector`` matches either end, because you look for a cable with "
        "USB-C on it and not for a direction."
    ),
)
async def list_cables(
    user: CurrentUser,
    session: SessionDep,
    q: Annotated[
        str | None, Query(description="Match the name, the brand, or the ends.")
    ] = None,
    kind: str | None = None,
    connector: Annotated[str | None, Query(description="Match either end.")] = None,
    location_id: uuid.UUID | None = None,
    item_id: uuid.UUID | None = None,
) -> Envelope[list[CableRead]]:
    statement = select(Cable).where(
        Cable.user_id == user.id, Cable.deleted_at.is_(None)
    )
    if q and q.strip():
        like = f"%{q.strip()}%"
        statement = statement.where(
            or_(
                Cable.name.ilike(like),
                Cable.brand.ilike(like),
                Cable.specification.ilike(like),
                Cable.connector_a.ilike(like),
                Cable.connector_b.ilike(like),
            )
        )
    if kind:
        statement = statement.where(Cable.kind == kind)
    if connector and connector.strip():
        end = f"%{connector.strip()}%"
        statement = statement.where(
            or_(Cable.connector_a.ilike(end), Cable.connector_b.ilike(end))
        )
    if location_id is not None:
        statement = statement.where(Cable.location_id == location_id)
    if item_id is not None:
        statement = statement.where(Cable.item_id == item_id)

    rows = (
        (await session.execute(statement.order_by(Cable.kind, Cable.name)))
        .scalars()
        .all()
    )
    places, items = await _names(session, user)
    return ok([_read(row, places, items) for row in rows])


@router.get(
    "/kinds",
    response_model=Envelope[list[str]],
    summary="List the cable families that are in use.",
)
async def list_kinds(user: CurrentUser, session: SessionDep) -> Envelope[list[str]]:
    rows = await session.execute(
        select(Cable.kind)
        .where(
            Cable.user_id == user.id,
            Cable.deleted_at.is_(None),
            Cable.kind.is_not(None),
        )
        .group_by(Cable.kind)
        .order_by(func.lower(Cable.kind))
    )
    return ok([row[0] for row in rows])


@router.post(
    "",
    response_model=Envelope[CableRead],
    status_code=status.HTTP_201_CREATED,
    summary="Add one cable.",
)
async def create_cable(
    body: CableCreate, user: CurrentUser, session: SessionDep
) -> Envelope[CableRead]:
    await _check_links(session, user, body.location_id, body.item_id)

    cable = Cable(user_id=user.id, **body.model_dump())
    cable.name = cable.name.strip()
    session.add(cable)
    await session.commit()
    await session.refresh(cable)

    places, items = await _names(session, user)
    return ok(_read(cable, places, items))


@router.get(
    "/{cable_id}",
    response_model=Envelope[CableRead],
    summary="Return one cable.",
)
async def get_cable(
    cable_id: uuid.UUID, user: CurrentUser, session: SessionDep
) -> Envelope[CableRead]:
    cable = await _get_cable_or_404(session, cable_id, user)
    places, items = await _names(session, user)
    return ok(_read(cable, places, items))


@router.put(
    "/{cable_id}",
    response_model=Envelope[CableRead],
    summary="Change a cable.",
)
async def update_cable(
    cable_id: uuid.UUID,
    body: CableUpdate,
    user: CurrentUser,
    session: SessionDep,
) -> Envelope[CableRead]:
    cable = await _get_cable_or_404(session, cable_id, user)
    fields = body.model_dump(exclude_unset=True)
    await _check_links(
        session,
        user,
        fields.get("location_id") if "location_id" in fields else None,
        fields.get("item_id") if "item_id" in fields else None,
    )

    for field, value in fields.items():
        setattr(cable, field, value.strip() if field == "name" and value else value)
    cable.version += 1
    await session.commit()
    await session.refresh(cable)

    places, items = await _names(session, user)
    return ok(_read(cable, places, items))


@router.delete(
    "/{cable_id}",
    response_model=Envelope[Message],
    summary="Delete a cable.",
)
async def delete_cable(
    cable_id: uuid.UUID, user: CurrentUser, session: SessionDep
) -> Envelope[Message]:
    cable = await _get_cable_or_404(session, cable_id, user)
    cable.deleted_at = datetime.now(UTC)
    cable.version += 1
    await session.commit()
    return ok(Message(message="The cable is deleted."))
