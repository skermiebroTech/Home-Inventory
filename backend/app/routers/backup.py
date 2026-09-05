"""Backup routes."""

from __future__ import annotations

import json
import logging
import shutil
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Annotated, Any

import anyio.to_thread
from fastapi import APIRouter, File, UploadFile, status

from app.config import settings
from app.schemas.backup import BackupFile, BackupSchedule, BackupStatus
from app.schemas.common import Envelope, Message, ok
from app.services.backup_service import BackupService, get_backup_service
from app.services.errors import ServiceError, to_api_error
from app.services.export_service import SCHEMA_VERSION
from app.utils.auth import CurrentUser, SessionDep, require_admin
from app.utils.errors import ApiError
from app.utils.queries import read_upload

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/backup", tags=["Backup"])

#: A restore archive holds every photograph, so it may be far larger than an
#: image upload.
MAX_RESTORE_BYTES = 4 * 1024 * 1024 * 1024


def _status(service: BackupService) -> BackupStatus:
    """Turn the service state into the API shape."""
    state = service.status()
    last = state.get("last_run") or {}
    return BackupStatus(
        schedule=BackupSchedule(
            enabled=bool(state["enabled"]),
            cron=str(state["cron"]),
            retention=int(state["retention"]),
            rclone_remote=state["rclone_remote"],
        ),
        last_run_at=_moment(last.get("finished_at")),
        last_run_ok=last.get("ok"),
        last_run_error=last.get("error"),
        next_run_at=_moment(state.get("next_run_at")),
        backups=[
            BackupFile(
                filename=str(entry["filename"]),
                size_bytes=int(entry["size_bytes"]),
                created_at=datetime.fromisoformat(str(entry["created_at"])),
            )
            for entry in state["backups"]
        ],
        backup_dir=str(state["backup_dir"]),
    )


def _moment(value: Any) -> datetime | None:
    """Read a timestamp out of the stored state."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return None


@router.get(
    "/status",
    response_model=Envelope[BackupStatus],
    summary="Report the backup schedule and the archives on disk.",
)
async def backup_status(
    user: CurrentUser, session: SessionDep
) -> Envelope[BackupStatus]:
    return ok(_status(get_backup_service()))


@router.post(
    "/schedule",
    response_model=Envelope[BackupStatus],
    summary="Set the automatic backup schedule.",
)
async def set_backup_schedule(
    body: BackupSchedule, user: CurrentUser, session: SessionDep
) -> Envelope[BackupStatus]:
    service = get_backup_service()
    try:
        service.reschedule(
            enabled=body.enabled,
            cron=body.cron,
            retention=body.retention,
            rclone_remote=body.rclone_remote or "",
        )
    except ServiceError as exc:
        raise to_api_error(exc) from exc
    return ok(_status(service))


@router.post(
    "/run",
    response_model=Envelope[Message],
    summary="Run a backup now.",
    description=(
        "This route is not in the original route list. The settings page "
        "needs a way to test the schedule without waiting for the cron time."
    ),
)
async def run_backup_now(user: CurrentUser, session: SessionDep) -> Envelope[Message]:
    run = await get_backup_service().run_now()
    if not run.ok:
        raise ApiError(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "backup_failed",
            run.error or "The backup failed.",
        )
    parts = [f"The backup wrote {run.path.name if run.path else 'the archive'}."]
    if run.pushed_to:
        parts.append(f"It was copied to {run.pushed_to}.")
    if run.deleted:
        parts.append(f"{len(run.deleted)} old archives were removed.")
    if run.warnings:
        parts.append(" ".join(run.warnings))
    return ok(Message(message=" ".join(parts)))


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
    # A restore replaces every row and every file, so it is an admin action.
    require_admin(user)

    data = await read_upload(file, max_bytes=MAX_RESTORE_BYTES, images_only=False)
    workdir = Path(tempfile.mkdtemp(prefix="homestock-restore-"))
    try:
        archive_path = workdir / "backup.zip"
        archive_path.write_bytes(data)
        notes = await anyio.to_thread.run_sync(
            lambda: _restore_files(archive_path, workdir)
        )
    finally:
        shutil.rmtree(workdir, ignore_errors=True)

    return ok(Message(message=" ".join(notes)))


def _restore_files(archive_path: Path, workdir: Path) -> list[str]:
    """Read the archive, check it, and put the uploads back.

    The database itself is restored with ``psql``, which the container ships
    with the PostgreSQL client. If ``psql`` is absent, the uploads still come
    back and the message says what the operator must do by hand.
    """
    notes: list[str] = []
    try:
        with zipfile.ZipFile(archive_path) as archive:
            names = set(archive.namelist())
            if "metadata.json" not in names:
                raise ApiError(
                    status.HTTP_422_UNPROCESSABLE_ENTITY,
                    "bad_archive",
                    "This ZIP holds no metadata.json, so it is not a HomeStock backup.",
                )
            metadata = json.loads(archive.read("metadata.json"))
            version = str(metadata.get("schema_version", ""))
            if version != SCHEMA_VERSION:
                raise ApiError(
                    status.HTTP_409_CONFLICT,
                    "schema_mismatch",
                    f"The archive uses schema version {version or 'unknown'}. "
                    f"This server reads version {SCHEMA_VERSION}.",
                )

            uploads = [name for name in names if name.startswith("uploads/")]
            for name in uploads:
                archive.extract(name, workdir)
            if uploads:
                _merge_uploads(workdir / "uploads", settings.upload_dir)
                notes.append(f"{len(uploads)} files were restored to the uploads.")

            if "database.sql" in names:
                archive.extract("database.sql", workdir)
                notes.append(_restore_database(workdir / "database.sql"))
            else:
                notes.append("The archive holds no database.sql, so no rows changed.")
    except zipfile.BadZipFile as exc:
        raise ApiError(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "bad_archive",
            "The uploaded file is not a readable ZIP.",
        ) from exc
    return notes


def _merge_uploads(source: Path, target: Path) -> None:
    """Copy the restored files over the live upload directory."""
    target.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, target, dirs_exist_ok=True)


def _restore_database(dump: Path) -> str:
    """Load a pg_dump file back into the database with psql."""
    import subprocess

    if shutil.which("psql") is None:
        return (
            "psql is not installed here, so the rows were not restored. Load "
            f"database.sql by hand: psql -f {dump.name}"
        )
    result = subprocess.run(
        [
            "psql",
            "--quiet",
            "--dbname",
            settings.sync_database_url,
            "--file",
            str(dump),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        logger.error("The restore failed: %s", result.stderr[:500])
        raise ApiError(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "restore_failed",
            f"psql refused the dump: {result.stderr.strip()[:300]}",
        )
    return "The database rows were restored."
