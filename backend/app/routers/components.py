"""Component routes: the catalogue, what is fitted to an item, and the spares."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import selectinload

from app.models.component import Component, ComponentSpare, ItemComponent
from app.models.item import Item
from app.models.location import Location
from app.models.user import User
from app.schemas.common import Envelope, Message, ok
from app.schemas.component import (
    ComponentCreate,
    ComponentDetail,
    ComponentRead,
    ComponentUpdate,
    ComponentUse,
    ItemComponentRead,
    ItemComponentUpdate,
    ItemComponentWrite,
    SpareRead,
    SpareUpdate,
    SpareUse,
    SpareWrite,
)
from app.utils.auth import CurrentUser, SessionDep
from app.utils.errors import ApiError, conflict, not_found
from app.utils.queries import get_item_or_404, get_location_or_404

router = APIRouter(prefix="/api", tags=["Components"])


# --------------------------------------------------------------------------
# Shared readers
# --------------------------------------------------------------------------


async def _get_component_or_404(
    session: SessionDep, component_id: uuid.UUID, user: User
) -> Component:
    """Return one live catalogue entry of this user, or raise 404."""
    component = (
        await session.execute(
            select(Component).where(
                Component.id == component_id,
                Component.user_id == user.id,
                Component.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if component is None:
        raise not_found("The component")
    return component


def _effective(price: Decimal | None, default: Decimal | None) -> Decimal | None:
    """Return the price of this one, or the default of the catalogue."""
    return price if price is not None else default


def _fitted_read(row: ItemComponent, component: Component) -> ItemComponentRead:
    """Build the reply for one fitted component."""
    read = ItemComponentRead.model_validate(row)
    read.name = component.name
    read.brand = component.brand
    read.model_number = component.model_number
    read.is_consumable = component.is_consumable
    read.default_price = component.default_price
    read.effective_price = _effective(row.price, component.default_price)
    read.line_total = (
        read.effective_price * row.quantity
        if read.effective_price is not None
        else None
    )
    return read


def _spare_read(
    row: ComponentSpare, component: Component, location_name: str | None
) -> SpareRead:
    """Build the reply for one row of stock."""
    read = SpareRead.model_validate(row)
    read.name = component.name
    read.brand = component.brand
    read.model_number = component.model_number
    read.is_consumable = component.is_consumable
    read.default_price = component.default_price
    read.effective_price = _effective(row.unit_price, component.default_price)
    read.stock_value = (
        read.effective_price * row.quantity
        if read.effective_price is not None
        else None
    )
    read.location_name = location_name
    read.is_low = row.is_low
    return read


def _place(names: dict[uuid.UUID, str], spare: ComponentSpare) -> str | None:
    """Return the name of the place that holds this stock, if it has one."""
    return names.get(spare.location_id) if spare.location_id else None


async def _location_names(session: SessionDep, user: User) -> dict[uuid.UUID, str]:
    """Return the name of every location of this user, by id."""
    rows = await session.execute(
        select(Location.id, Location.name).where(Location.user_id == user.id)
    )
    return {row[0]: row[1] for row in rows}


# --------------------------------------------------------------------------
# The catalogue
# --------------------------------------------------------------------------


@router.get(
    "/components",
    response_model=Envelope[list[ComponentRead]],
    summary="List the component catalogue.",
)
async def list_components(
    user: CurrentUser,
    session: SessionDep,
    q: Annotated[
        str | None, Query(description="Match the name, brand, or model.")
    ] = None,
    category: str | None = None,
    consumable: Annotated[bool | None, Query()] = None,
) -> Envelope[list[ComponentRead]]:
    statement = select(Component).where(
        Component.user_id == user.id, Component.deleted_at.is_(None)
    )
    if q and q.strip():
        like = f"%{q.strip()}%"
        statement = statement.where(
            or_(
                Component.name.ilike(like),
                Component.brand.ilike(like),
                Component.model_number.ilike(like),
            )
        )
    if category:
        statement = statement.where(Component.category == category)
    if consumable is not None:
        statement = statement.where(Component.is_consumable.is_(consumable))

    rows = (await session.execute(statement.order_by(Component.name))).scalars().all()
    return ok([ComponentRead.model_validate(row) for row in rows])


@router.post(
    "/components",
    response_model=Envelope[ComponentRead],
    status_code=status.HTTP_201_CREATED,
    summary="Add one kind of part to the catalogue.",
)
async def create_component(
    body: ComponentCreate, user: CurrentUser, session: SessionDep
) -> Envelope[ComponentRead]:
    component = Component(user_id=user.id, **body.model_dump())
    component.name = component.name.strip()
    session.add(component)
    await session.commit()
    await session.refresh(component)
    return ok(ComponentRead.model_validate(component))


@router.get(
    "/components/{component_id}",
    response_model=Envelope[ComponentDetail],
    summary="Return one catalogue entry, with where it is used.",
)
async def get_component(
    component_id: uuid.UUID, user: CurrentUser, session: SessionDep
) -> Envelope[ComponentDetail]:
    component = await _get_component_or_404(session, component_id, user)

    uses = (
        await session.execute(
            select(ItemComponent.item_id, Item.name, ItemComponent.quantity)
            .join(Item, Item.id == ItemComponent.item_id)
            .where(
                ItemComponent.component_id == component_id,
                ItemComponent.deleted_at.is_(None),
                Item.deleted_at.is_(None),
            )
            .order_by(Item.name)
        )
    ).all()
    spare_total = await session.scalar(
        select(func.coalesce(func.sum(ComponentSpare.quantity), 0)).where(
            ComponentSpare.component_id == component_id,
            ComponentSpare.deleted_at.is_(None),
        )
    )

    detail = ComponentDetail.model_validate(component)
    detail.fitted_to = [
        ComponentUse(item_id=row[0], item_name=row[1], quantity=row[2]) for row in uses
    ]
    detail.fitted_count = sum(use.quantity for use in detail.fitted_to)
    detail.spare_quantity = int(spare_total or 0)
    return ok(detail)


@router.put(
    "/components/{component_id}",
    response_model=Envelope[ComponentRead],
    summary="Change a catalogue entry.",
)
async def update_component(
    component_id: uuid.UUID,
    body: ComponentUpdate,
    user: CurrentUser,
    session: SessionDep,
) -> Envelope[ComponentRead]:
    component = await _get_component_or_404(session, component_id, user)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(component, field, value.strip() if field == "name" and value else value)
    component.version += 1
    await session.commit()
    await session.refresh(component)
    return ok(ComponentRead.model_validate(component))


@router.delete(
    "/components/{component_id}",
    response_model=Envelope[Message],
    summary="Delete a catalogue entry.",
    description=(
        "An entry that an item still uses cannot go. Remove it from those "
        "items first, or the history of what they are made of would break."
    ),
)
async def delete_component(
    component_id: uuid.UUID, user: CurrentUser, session: SessionDep
) -> Envelope[Message]:
    component = await _get_component_or_404(session, component_id, user)

    in_use = await session.scalar(
        select(func.count())
        .select_from(ItemComponent)
        .where(
            ItemComponent.component_id == component_id,
            ItemComponent.deleted_at.is_(None),
        )
    )
    if in_use:
        raise conflict(
            f"{in_use} items still carry this component. Take it off them first."
        )

    moment = datetime.now(UTC)
    component.deleted_at = moment
    component.version += 1
    # The stock of a part that no longer exists goes with it.
    spares = (
        (
            await session.execute(
                select(ComponentSpare).where(
                    ComponentSpare.component_id == component_id,
                    ComponentSpare.deleted_at.is_(None),
                )
            )
        )
        .scalars()
        .all()
    )
    for spare in spares:
        spare.deleted_at = moment
        spare.version += 1

    await session.commit()
    return ok(Message(message="The component is deleted."))


# --------------------------------------------------------------------------
# Fitted to an item
# --------------------------------------------------------------------------


@router.get(
    "/items/{item_id}/components",
    response_model=Envelope[list[ItemComponentRead]],
    summary="List what one item is made of.",
)
async def list_item_components(
    item_id: uuid.UUID, user: CurrentUser, session: SessionDep
) -> Envelope[list[ItemComponentRead]]:
    await get_item_or_404(session, item_id, user)
    rows = (
        (
            await session.execute(
                select(ItemComponent)
                .where(
                    ItemComponent.item_id == item_id,
                    ItemComponent.deleted_at.is_(None),
                )
                .options(selectinload(ItemComponent.component))
                .order_by(ItemComponent.created_at)
            )
        )
        .scalars()
        .all()
    )
    return ok([_fitted_read(row, row.component) for row in rows])


@router.post(
    "/items/{item_id}/components",
    response_model=Envelope[ItemComponentRead],
    status_code=status.HTTP_201_CREATED,
    summary="Fit a component to an item.",
)
async def add_item_component(
    item_id: uuid.UUID,
    body: ItemComponentWrite,
    user: CurrentUser,
    session: SessionDep,
) -> Envelope[ItemComponentRead]:
    item = await get_item_or_404(session, item_id, user)
    component = await _get_component_or_404(session, body.component_id, user)

    fitted = ItemComponent(item_id=item.id, **body.model_dump())
    session.add(fitted)
    # A new part changes what the item is, so the mobile copy must hear of it.
    item.version += 1
    await session.commit()
    await session.refresh(fitted)
    return ok(_fitted_read(fitted, component))


@router.put(
    "/item-components/{fitted_id}",
    response_model=Envelope[ItemComponentRead],
    summary="Change a fitted component.",
)
async def update_item_component(
    fitted_id: uuid.UUID,
    body: ItemComponentUpdate,
    user: CurrentUser,
    session: SessionDep,
) -> Envelope[ItemComponentRead]:
    fitted = await _get_fitted_or_404(session, fitted_id, user)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(fitted, field, value)
    fitted.version += 1
    await session.commit()
    await session.refresh(fitted)
    component = await _get_component_or_404(session, fitted.component_id, user)
    return ok(_fitted_read(fitted, component))


@router.delete(
    "/item-components/{fitted_id}",
    response_model=Envelope[Message],
    summary="Take a component off an item.",
)
async def remove_item_component(
    fitted_id: uuid.UUID, user: CurrentUser, session: SessionDep
) -> Envelope[Message]:
    fitted = await _get_fitted_or_404(session, fitted_id, user)
    fitted.deleted_at = datetime.now(UTC)
    fitted.version += 1
    await session.commit()
    return ok(Message(message="The component is off the item."))


async def _get_fitted_or_404(
    session: SessionDep, fitted_id: uuid.UUID, user: User
) -> ItemComponent:
    """Return one fitted component of this user, or raise 404."""
    fitted = (
        await session.execute(
            select(ItemComponent)
            .join(Item, Item.id == ItemComponent.item_id)
            .where(
                ItemComponent.id == fitted_id,
                ItemComponent.deleted_at.is_(None),
                Item.user_id == user.id,
                Item.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if fitted is None:
        raise not_found("That fitted component")
    return fitted


# --------------------------------------------------------------------------
# Spares
# --------------------------------------------------------------------------


@router.get(
    "/spares",
    response_model=Envelope[list[SpareRead]],
    summary="List the spare parts and the consumables on the shelf.",
    description="The rows that ran low come first.",
)
async def list_spares(
    user: CurrentUser,
    session: SessionDep,
    low_only: Annotated[bool, Query(description="Only the rows that ran low.")] = False,
    consumable: Annotated[bool | None, Query()] = None,
) -> Envelope[list[SpareRead]]:
    statement = (
        select(ComponentSpare)
        .join(Component, Component.id == ComponentSpare.component_id)
        .where(
            ComponentSpare.user_id == user.id,
            ComponentSpare.deleted_at.is_(None),
            Component.deleted_at.is_(None),
        )
        .options(selectinload(ComponentSpare.component))
    )
    if consumable is not None:
        statement = statement.where(Component.is_consumable.is_(consumable))

    rows = (await session.execute(statement.order_by(Component.name))).scalars().all()
    names = await _location_names(session, user)

    spares = [_spare_read(row, row.component, _place(names, row)) for row in rows]
    if low_only:
        spares = [spare for spare in spares if spare.is_low]
    # What ran out is what the page is for, so it goes first.
    spares.sort(key=lambda spare: (not spare.is_low, spare.name.lower()))
    return ok(spares)


@router.post(
    "/spares",
    response_model=Envelope[SpareRead],
    status_code=status.HTTP_201_CREATED,
    summary="Put stock of a component on the shelf.",
)
async def create_spare(
    body: SpareWrite, user: CurrentUser, session: SessionDep
) -> Envelope[SpareRead]:
    component = await _get_component_or_404(session, body.component_id, user)
    if body.location_id is not None:
        await get_location_or_404(session, body.location_id, user)

    existing = (
        await session.execute(
            select(ComponentSpare).where(
                ComponentSpare.component_id == body.component_id,
                ComponentSpare.location_id == body.location_id,
                ComponentSpare.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise conflict(
            "That component already has stock in that place. Change the count "
            "on the row that is there."
        )

    spare = ComponentSpare(user_id=user.id, **body.model_dump())
    session.add(spare)
    await session.commit()
    await session.refresh(spare)
    names = await _location_names(session, user)
    return ok(_spare_read(spare, component, _place(names, spare)))


@router.put(
    "/spares/{spare_id}",
    response_model=Envelope[SpareRead],
    summary="Change a row of stock.",
)
async def update_spare(
    spare_id: uuid.UUID,
    body: SpareUpdate,
    user: CurrentUser,
    session: SessionDep,
) -> Envelope[SpareRead]:
    spare = await _get_spare_or_404(session, spare_id, user)
    changes = body.model_dump(exclude_unset=True)
    if changes.get("location_id") is not None:
        await get_location_or_404(session, changes["location_id"], user)
    for field, value in changes.items():
        setattr(spare, field, value)
    spare.version += 1
    await session.commit()
    await session.refresh(spare)
    component = await _get_component_or_404(session, spare.component_id, user)
    names = await _location_names(session, user)
    return ok(_spare_read(spare, component, _place(names, spare)))


@router.post(
    "/spares/{spare_id}/use",
    response_model=Envelope[SpareRead],
    summary="Take stock off the shelf.",
    description=(
        "This is the one action a consumable needs: you fitted a filter, so "
        "the count goes down by one. A negative count puts stock back."
    ),
)
async def use_spare(
    spare_id: uuid.UUID,
    body: SpareUse,
    user: CurrentUser,
    session: SessionDep,
) -> Envelope[SpareRead]:
    spare = await _get_spare_or_404(session, spare_id, user)
    remaining = spare.quantity - body.count
    if remaining < 0:
        raise ApiError(
            status.HTTP_409_CONFLICT,
            "not_enough_stock",
            f"Only {spare.quantity} left, and you asked for {body.count}.",
        )

    spare.quantity = remaining
    if body.note:
        stamp = datetime.now(UTC).date().isoformat()
        line = f"{stamp}: {body.note.strip()}"
        spare.notes = f"{spare.notes}\n{line}" if spare.notes else line
    spare.version += 1

    await session.commit()
    await session.refresh(spare)
    component = await _get_component_or_404(session, spare.component_id, user)
    names = await _location_names(session, user)
    return ok(_spare_read(spare, component, _place(names, spare)))


@router.delete(
    "/spares/{spare_id}",
    response_model=Envelope[Message],
    summary="Remove a row of stock.",
)
async def delete_spare(
    spare_id: uuid.UUID, user: CurrentUser, session: SessionDep
) -> Envelope[Message]:
    spare = await _get_spare_or_404(session, spare_id, user)
    spare.deleted_at = datetime.now(UTC)
    spare.version += 1
    await session.commit()
    return ok(Message(message="The stock row is removed."))


async def _get_spare_or_404(
    session: SessionDep, spare_id: uuid.UUID, user: User
) -> ComponentSpare:
    """Return one row of stock of this user, or raise 404."""
    spare = (
        await session.execute(
            select(ComponentSpare).where(
                ComponentSpare.id == spare_id,
                ComponentSpare.user_id == user.id,
                ComponentSpare.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if spare is None:
        raise not_found("That row of stock")
    return spare


__all__ = ["router"]
