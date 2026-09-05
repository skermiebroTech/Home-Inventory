"""Delta sync routes for the offline-first mobile application."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Query

from app.schemas.common import Envelope
from app.schemas.sync import SyncChanges, SyncPush, SyncPushResult
from app.utils.auth import CurrentUser, SessionDep
from app.utils.errors import not_implemented

router = APIRouter(prefix="/api/sync", tags=["Sync"])


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
    not_implemented("GET /api/sync/changes")


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
    not_implemented("POST /api/sync/push")
