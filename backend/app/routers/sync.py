"""Delta sync routes for the offline-first mobile application."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Query

from app.models.component import Component, ComponentSpare, ItemComponent
from app.models.custom_field import CustomField
from app.models.item import Item, ItemPhoto
from app.models.location import Location
from app.models.maintenance import MaintenanceLog
from app.models.receipt import Receipt
from app.models.tag import Tag
from app.schemas.common import Envelope, ok
from app.schemas.component import ComponentRead, ItemComponentRow, SpareRow
from app.schemas.custom_field import CustomFieldRead
from app.schemas.item import ItemPhotoRead, ItemRead
from app.schemas.location import LocationRead
from app.schemas.maintenance import MaintenanceRead
from app.schemas.receipt import ReceiptRead
from app.schemas.sync import (
    SyncChange,
    SyncChanges,
    SyncConflict,
    SyncEntity,
    SyncError,
    SyncPush,
    SyncPushResult,
)
from app.schemas.tag import TagRead
from app.services.errors import ServiceError, to_api_error
from app.services.sync_service import (
    ParentScope,
    SyncRegistry,
    SyncResource,
    apply_push,
    fetch_changes,
    utc_now,
)
from app.utils.auth import CurrentUser, SessionDep

router = APIRouter(prefix="/api/sync", tags=["Sync"])

#: The tables that the mobile application mirrors, and how each one reaches
#: the user who owns it. A child table names its parent, so that a client can
#: never read or write a row of another account.
REGISTRY = SyncRegistry(
    [
        SyncResource(name=SyncEntity.LOCATION.value, model=Location),
        SyncResource(name=SyncEntity.ITEM.value, model=Item, load=("tags",)),
        SyncResource(
            name=SyncEntity.ITEM_PHOTO.value,
            model=ItemPhoto,
            user_column=None,
            parent=ParentScope(foreign_key="item_id", model=Item),
        ),
        # Tags are shared across the household, so they have no owner column.
        SyncResource(name=SyncEntity.TAG.value, model=Tag, user_column=None),
        SyncResource(name=SyncEntity.RECEIPT.value, model=Receipt),
        SyncResource(
            name=SyncEntity.MAINTENANCE.value,
            model=MaintenanceLog,
            user_column=None,
            parent=ParentScope(foreign_key="item_id", model=Item),
        ),
        SyncResource(
            name=SyncEntity.CUSTOM_FIELD.value,
            model=CustomField,
            user_column=None,
            parent=ParentScope(foreign_key="item_id", model=Item),
        ),
        SyncResource(name=SyncEntity.COMPONENT.value, model=Component),
        SyncResource(
            name=SyncEntity.ITEM_COMPONENT.value,
            model=ItemComponent,
            user_column=None,
            parent=ParentScope(foreign_key="item_id", model=Item),
        ),
        SyncResource(name=SyncEntity.SPARE.value, model=ComponentSpare),
    ]
)

#: The names that `SyncEntity` accepts. A change with any other name failed
#: before it reached a resource, and it has no entity to report.
SYNC_ENTITIES: frozenset[str] = frozenset(entry.value for entry in SyncEntity)

#: Which response schema reads which table.
READERS: dict[str, Any] = {
    SyncEntity.LOCATION.value: LocationRead,
    SyncEntity.ITEM.value: ItemRead,
    SyncEntity.ITEM_PHOTO.value: ItemPhotoRead,
    SyncEntity.TAG.value: TagRead,
    SyncEntity.RECEIPT.value: ReceiptRead,
    SyncEntity.MAINTENANCE.value: MaintenanceRead,
    SyncEntity.CUSTOM_FIELD.value: CustomFieldRead,
    SyncEntity.COMPONENT.value: ComponentRead,
    SyncEntity.ITEM_COMPONENT.value: ItemComponentRow,
    SyncEntity.SPARE.value: SpareRow,
}

#: Which field of `SyncChanges` holds which table.
FIELDS: dict[str, str] = {
    SyncEntity.LOCATION.value: "locations",
    SyncEntity.ITEM.value: "items",
    SyncEntity.ITEM_PHOTO.value: "item_photos",
    SyncEntity.TAG.value: "tags",
    SyncEntity.RECEIPT.value: "receipts",
    SyncEntity.MAINTENANCE.value: "maintenance_logs",
    SyncEntity.CUSTOM_FIELD.value: "custom_fields",
    SyncEntity.COMPONENT.value: "components",
    SyncEntity.ITEM_COMPONENT.value: "item_components",
    SyncEntity.SPARE.value: "spares",
}


@router.get(
    "/changes",
    response_model=Envelope[SyncChanges],
    summary="Return everything that changed since a timestamp.",
    description=(
        "Omit ``since`` on the first sync to receive the whole dataset. Send "
        "back the ``server_time`` value from the reply on the next call. "
        "Deleted rows appear in the ``deleted`` map, because a hard delete "
        "could never reach the client."
    ),
)
async def get_changes(
    user: CurrentUser,
    session: SessionDep,
    since: Annotated[
        datetime | None,
        Query(description="An ISO 8601 timestamp from an earlier reply."),
    ] = None,
    limit: Annotated[int, Query(ge=1, le=5000)] = 1000,
) -> Envelope[SyncChanges]:
    # The timestamp is read before the queries run. A row written during the
    # sync then arrives on the next call, instead of being skipped.
    server_time = utc_now()
    changes = SyncChanges(since=since, server_time=server_time)

    for resource in REGISTRY:
        rows = await fetch_changes(
            session, resource, since=since, user_id=user.id, limit=limit
        )
        reader = READERS[resource.name]
        setattr(
            changes,
            FIELDS[resource.name],
            [reader.model_validate(row) for row in rows.updated],
        )
        if rows.deleted:
            changes.deleted[SyncEntity(resource.name)] = rows.deleted
        if rows.has_more:
            changes.has_more = True

    return ok(changes)


@router.post(
    "/push",
    response_model=Envelope[SyncPushResult],
    summary="Upload the changes that the client made while it was offline.",
    description=(
        "The server wins every conflict. A rejected change appears in "
        "``conflicts`` so that the client can tell the user."
    ),
)
async def push_changes(
    body: SyncPush, user: CurrentUser, session: SessionDep
) -> Envelope[SyncPushResult]:
    try:
        result = await apply_push(
            session,
            REGISTRY,
            [_to_change(change) for change in body.changes],
            user_id=user.id,
        )
    except ServiceError as exc:
        raise to_api_error(exc) from exc

    conflicts = [
        SyncConflict(
            entity=SyncEntity(outcome.resource),
            id=outcome.record_id,
            reason=outcome.conflict_reason or "The server record is newer.",
            server_version=outcome.version or 0,
        )
        for outcome in result.conflicts
    ]
    errors = [
        SyncError(
            entity=SyncEntity(outcome.resource),
            id=outcome.record_id,
            message=outcome.error or "The change did not apply.",
        )
        for outcome in result.errors
        if outcome.resource in SYNC_ENTITIES
    ]
    rejected = len(result.outcomes) - len(result.applied)

    return ok(
        SyncPushResult(
            applied=len(result.applied),
            rejected=rejected,
            conflicts=conflicts,
            errors=errors,
            server_time=result.server_time,
        )
    )


def _to_change(change: SyncChange) -> dict[str, Any]:
    """Turn one API change into the shape that the sync service reads."""
    return {
        "resource": change.entity.value,
        "op": change.op.value,
        "id": change.id,
        "data": change.payload or {},
        "base_version": change.base_version,
        "base_updated_at": change.client_updated_at,
    }
