"""The activity log routes."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Query
from sqlalchemy import select

from app.models.activity import Activity
from app.schemas.activity import ActivityRow
from app.schemas.common import Envelope, ok
from app.utils.auth import CurrentUser, SessionDep
from app.utils.queries import get_item_or_404

router = APIRouter(prefix="/api", tags=["Activity"])


@router.get(
    "/items/{item_id}/activity",
    response_model=Envelope[list[ActivityRow]],
    summary="Return the log of one item. The newest line comes first.",
)
async def item_activity(
    item_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> Envelope[list[ActivityRow]]:
    # The check answers 404 for an item of another account, before the log
    # of that item could say that it exists.
    await get_item_or_404(session, item_id, user)

    rows = await session.execute(
        select(Activity)
        .where(
            Activity.user_id == user.id,
            Activity.entity_type == "item",
            Activity.entity_id == item_id,
            Activity.deleted_at.is_(None),
        )
        .order_by(Activity.created_at.desc())
        .limit(limit)
    )
    return ok([ActivityRow.model_validate(row) for row in rows.scalars().all()])


@router.get(
    "/activity",
    response_model=Envelope[list[ActivityRow]],
    summary="Return the newest lines of the whole log.",
)
async def recent_activity(
    user: CurrentUser,
    session: SessionDep,
    action: Annotated[str | None, Query(description="Only this kind of line.")] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
) -> Envelope[list[ActivityRow]]:
    statement = select(Activity).where(
        Activity.user_id == user.id, Activity.deleted_at.is_(None)
    )
    if action:
        statement = statement.where(Activity.action == action)

    rows = await session.execute(
        statement.order_by(Activity.created_at.desc()).limit(limit)
    )
    return ok([ActivityRow.model_validate(row) for row in rows.scalars().all()])
