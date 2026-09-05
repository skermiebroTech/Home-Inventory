"""Backup schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class BackupSchedule(BaseModel):
    """How and when the automatic backup runs."""

    enabled: bool = False
    cron: str = Field(default="0 3 * * *", description="A five field cron expression.")
    retention: int = Field(default=7, ge=1, le=365)
    rclone_remote: str | None = Field(
        default=None, description="For example: b2:my-bucket/homestock"
    )


class BackupFile(BaseModel):
    """One backup archive on disk."""

    filename: str
    size_bytes: int
    created_at: datetime


class BackupStatus(BaseModel):
    """The reply from GET /api/backup/status."""

    schedule: BackupSchedule
    last_run_at: datetime | None = None
    last_run_ok: bool | None = None
    last_run_error: str | None = None
    next_run_at: datetime | None = None
    backups: list[BackupFile] = Field(default_factory=list)
    backup_dir: str
