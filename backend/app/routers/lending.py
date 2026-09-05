"""Lending routes.

``GET /api/items/lent`` has a fixed path that would otherwise match
``GET /api/items/{item_id}``. ``main.py`` registers this router before the
items router so that the fixed path wins.
"""

from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.item import Item
from app.schemas.common import Envelope, ok
from app.schemas.item import ItemDetail, ItemRead, LendRequest
from app.utils.auth import CurrentUser, SessionDep
from app.utils.errors import conflict
from app.utils.queries import (
    get_item_or_404,
    reload_item,
    to_item_detail,
    to_item_read,
)

router = APIRouter(prefix="/api", tags=["Lending"])


@router.get(
    "/items/lent",
    response_model=Envelope[list[ItemRead]],
    summary="List every item that is out on loan.",
)
async def list_lent_items(
    user: CurrentUser, session: SessionDep
) -> Envelope[list[ItemRead]]:
    rows = (
        (
            await session.execute(
                select(Item)
                .where(
                    Item.user_id == user.id,
                    Item.deleted_at.is_(None),
                    Item.is_lent.is_(True),
                )
                .options(selectinload(Item.photos), selectinload(Item.tags))
                .order_by(Item.lent_date.asc().nullslast(), Item.name)
            )
        )
        .scalars()
        .all()
    )
    return ok([to_item_read(row) for row in rows])


@router.post(
    "/items/{item_id}/lend",
    response_model=Envelope[ItemDetail],
    summary="Lend an item to a person.",
)
async def lend_item(
    item_id: uuid.UUID, body: LendRequest, user: CurrentUser, session: SessionDep
) -> Envelope[ItemDetail]:
    item = await get_item_or_404(session, item_id, user, with_relations=True)
    if item.is_lent:
        raise conflict(f"This item is already with {item.lent_to}.")

    item.is_lent = True
    item.lent_to = body.lent_to.strip()
    item.lent_date = body.lent_date or date.today()
    if body.notes:
        # The note joins the item notes, so that the record survives the
        # return. The items table holds no separate lending note column.
        line = f"Lent to {item.lent_to} on {item.lent_date}: {body.notes.strip()}"
        item.notes = f"{item.notes}\n{line}" if item.notes else line
    item.version += 1

    await session.commit()
    await reload_item(session, item)
    return ok(await to_item_detail(session, item))


@router.post(
    "/items/{item_id}/return",
    response_model=Envelope[ItemDetail],
    summary="Mark a lent item as returned.",
)
async def return_item(
    item_id: uuid.UUID, user: CurrentUser, session: SessionDep
) -> Envelope[ItemDetail]:
    item = await get_item_or_404(session, item_id, user, with_relations=True)
    if not item.is_lent:
        raise conflict("This item is not out on loan.")

    item.is_lent = False
    item.lent_to = None
    item.lent_date = None
    item.version += 1

    await session.commit()
    await reload_item(session, item)
    return ok(await to_item_detail(session, item))
