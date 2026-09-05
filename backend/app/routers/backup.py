"""Backup routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, File, UploadFile

from app.schemas.backup import BackupSchedule, BackupStatus
from app.schemas.common import Envelope, Message
from app.utils.auth import CurrentUser, SessionDep
from app.utils.errors import not_implemented

router = APIRouter(prefix="/api/backup", tags=["Backup"])


@router.get(
    "/status",
    response_model=Envelope[BackupStatus],
    summary="Report the backup schedule and the archives on disk.",
)
async def backup_status(
    user: CurrentUser, session: SessionDep
) -> Envelope[BackupStatus]:
    not_implemented("GET /api/backup/status")


@router.post(
    "/schedule",
    response_model=Envelope[BackupStatus],
    summary="Set the automatic backup schedule.",
)
async def set_backup_schedule(
    body: BackupSchedule, user: CurrentUser, session: SessionDep
) -> Envelope[BackupStatus]:
    not_implemented("POST /api/backup/schedule")


@router.post(
    "/run",
    response_model=Envelope[Message],
    summary="Run a backup now.",
    description=(
        "This route is not in the original route list. The settings page "
        "needs a way to test the schedule without waiting for the cron time."
    ),
)
async def run_backup_now(
    user: CurrentUser, session: SessionDep
) -> Envelope[Message]:
    not_implemented("POST /api/backup/run")


@router.post(
    "/restore",
    response_model=Envelope[Message],
    summary="Restore from a backup archive.",
    description=(
        "This replaces the database and the uploads. The server checks the "
        "schema version in metadata.json before it writes anything."
    ),
)
async def restore_backup(
    user: CurrentUser,
    session: SessionDep,
    file: Annotated[UploadFile, File(description="A ZIP from GET /api/export/full.")],
) -> Envelope[Message]:
    not_implemented("POST /api/backup/restore")
