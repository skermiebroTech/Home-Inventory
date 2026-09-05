"""Maintenance routes."""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from typing import Annotated

from fastapi import APIRouter, Query, status
from sqlalchemy import select

from app.models.item import Item
from app.models.maintenance import MaintenanceLog
from app.schemas.common import Envelope, ok
from app.schemas.maintenance import (
    MaintenanceCreate,
    MaintenanceDue,
    MaintenanceRead,
    MaintenanceUpdate,
)
from app.utils.auth import CurrentUser, SessionDep
from app.utils.errors import not_found
from app.utils.queries import get_item_or_404

router = APIRouter(prefix="/api", tags=["Maintenance"])


@router.get(
    "/maintenance/upcoming",
    response_model=Envelope[list[MaintenanceDue]],
    summary="List the service work that is due soon.",
)
async def upcoming_maintenance(
    user: CurrentUser,
    session: SessionDep,
    days: Annotated[int, Query(ge=1, le=365)] = 30,
) -> Envelope[list[MaintenanceDue]]:
    today = date.today()
    horizon = today + timedelta(days=days)

    rows = (
        await session.execute(
            select(MaintenanceLog, Item.name)
            .join(Item, Item.id == MaintenanceLog.item_id)
            .where(
                Item.user_id == user.id,
                Item.deleted_at.is_(None),
                MaintenanceLog.deleted_at.is_(None),
                MaintenanceLog.next_due_date.is_not(None),
                MaintenanceLog.next_due_date <= horizon,
            )
            .order_by(MaintenanceLog.next_due_date.asc())
        )
    ).all()

    due: list[MaintenanceDue] = []
    for log, item_name in rows:
        record = MaintenanceRead.model_validate(log)
        due.append(
            MaintenanceDue(
                **record.model_dump(),
                item_name=item_name,
                # Overdue work stays in the list, with a negative count.
                days_until_due=(log.next_due_date - today).days,
            )
        )
    return ok(due)


@router.get(
    "/items/{item_id}/maintenance",
    response_model=Envelope[list[MaintenanceRead]],
    summary="List the service history of one item.",
)
async def list_item_maintenance(
    item_id: uuid.UUID, user: CurrentUser, session: SessionDep
) -> Envelope[list[MaintenanceRead]]:
    await get_item_or_404(session, item_id, user)
    rows = (
        (
            await session.execute(
                select(MaintenanceLog)
                .where(
                    MaintenanceLog.item_id == item_id,
                    MaintenanceLog.deleted_at.is_(None),
                )
                .order_by(
                    MaintenanceLog.date_performed.desc().nullslast(),
                    MaintenanceLog.created_at.desc(),
                )
            )
        )
        .scalars()
        .all()
    )
    return ok([MaintenanceRead.model_validate(row) for row in rows])


@router.post(
    "/items/{item_id}/maintenance",
    response_model=Envelope[MaintenanceRead],
    status_code=status.HTTP_201_CREATED,
    summary="Record service work on an item.",
)
async def create_item_maintenance(
    item_id: uuid.UUID,
    body: MaintenanceCreate,
    user: CurrentUser,
    session: SessionDep,
) -> Envelope[MaintenanceRead]:
    await get_item_or_404(session, item_id, user)
    log = MaintenanceLog(item_id=item_id, **body.model_dump())
    session.add(log)
    await session.commit()
    await session.refresh(log)
    return ok(MaintenanceRead.model_validate(log))


@router.put(
    "/maintenance/{maintenance_id}",
    response_model=Envelope[MaintenanceRead],
    summary="Change a maintenance record.",
)
async def update_maintenance(
    maintenance_id: uuid.UUID,
    body: MaintenanceUpdate,
    user: CurrentUser,
    session: SessionDep,
) -> Envelope[MaintenanceRead]:
    log = (
        await session.execute(
            select(MaintenanceLog)
            .join(Item, Item.id == MaintenanceLog.item_id)
            .where(
                MaintenanceLog.id == maintenance_id,
                MaintenanceLog.deleted_at.is_(None),
                Item.user_id == user.id,
                Item.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if log is None:
        raise not_found("The maintenance record")

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(log, field, value)
    log.version += 1

    await session.commit()
    await session.refresh(log)
    return ok(MaintenanceRead.model_validate(log))
