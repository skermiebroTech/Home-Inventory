"""Scheduled backup: APScheduler, a retention rule, and an rclone push.

The service does not know how to read the database. `main.py` gives it a
callback that writes one export ZIP to a path, and this module decides when to
call it, how many files to keep, and where to copy them.
"""

from __future__ import annotations

import asyncio
import json
import logging
import shutil
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

from app.services.errors import BackupError, ValidationError
from app.services.export_service import ExportResult, export_filename
from app.utils.settings import setting

logger = logging.getLogger(__name__)

DEFAULT_CRON: Final[str] = "0 3 * * *"
DEFAULT_RETENTION: Final[int] = 7
BACKUP_PREFIX: Final[str] = "homestock-backup"
STATE_FILENAME: Final[str] = "backup_state.json"
RCLONE_TIMEOUT: Final[float] = 1800.0

#: The callback writes one export to the given path.
ExportCallback = Callable[[Path], Awaitable[ExportResult]]


@dataclass(frozen=True, slots=True)
class BackupConfig:
    """How the scheduled backup behaves."""

    enabled: bool = False
    cron: str = DEFAULT_CRON
    retention: int = DEFAULT_RETENTION
    backup_dir: Path = Path("/data/backups")
    config_dir: Path = Path("/data/config")
    rclone_remote: str | None = None
    timezone: str | None = None

    @classmethod
    def from_settings(cls) -> BackupConfig:
        """Build the configuration from the environment."""
        return cls(
            enabled=bool(setting("backup_enabled", False)),
            cron=str(setting("backup_cron", DEFAULT_CRON) or DEFAULT_CRON),
            retention=int(
                setting("backup_retention", DEFAULT_RETENTION) or DEFAULT_RETENTION
            ),
            backup_dir=Path(str(setting("backup_dir", "/data/backups"))),
            config_dir=Path(str(setting("config_dir", "/data/config"))),
            rclone_remote=(str(setting("rclone_remote", "") or "") or None),
            timezone=(str(setting("tz", "") or "") or None),
        )

    def replace(self, **changes: Any) -> BackupConfig:
        """Return a copy with some fields changed."""
        from dataclasses import replace

        return replace(self, **changes)


@dataclass(frozen=True, slots=True)
class BackupRun:
    """The record of one backup attempt."""

    started_at: datetime
    finished_at: datetime
    ok: bool
    path: Path | None = None
    size_bytes: int = 0
    error: str | None = None
    pushed_to: str | None = None
    deleted: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        """Return the run as a plain dictionary."""
        return {
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat(),
            "ok": self.ok,
            "path": str(self.path) if self.path else None,
            "filename": self.path.name if self.path else None,
            "size_bytes": self.size_bytes,
            "error": self.error,
            "pushed_to": self.pushed_to,
            "deleted": list(self.deleted),
            "warnings": list(self.warnings),
        }


class BackupService:
    """Run the backup now, or on a schedule."""

    def __init__(
        self,
        export_callback: ExportCallback,
        *,
        config: BackupConfig | None = None,
    ) -> None:
        self.config = config or BackupConfig.from_settings()
        self._export = export_callback
        self._scheduler: Any = None
        self._lock = asyncio.Lock()
        self._last_run: BackupRun | None = None

    # -- lifecycle ---------------------------------------------------------

    def start(self) -> None:
        """Start the scheduler if the backup is on. Safe to call twice."""
        if not self.config.enabled:
            logger.info("The scheduled backup is off.")
            return
        if self._scheduler is not None:
            return
        self._scheduler = self._build_scheduler(self.config.cron)
        self._scheduler.start()
        logger.info(
            "The scheduled backup runs on the cron expression '%s'.", self.config.cron
        )

    async def shutdown(self) -> None:
        """Stop the scheduler."""
        if self._scheduler is not None:
            self._scheduler.shutdown(wait=False)
            self._scheduler = None

    def reschedule(
        self,
        *,
        enabled: bool | None = None,
        cron: str | None = None,
        retention: int | None = None,
        rclone_remote: str | None = None,
    ) -> BackupConfig:
        """Change the schedule at run time. `POST /api/backup/schedule` calls this."""
        changes: dict[str, Any] = {}
        if cron is not None:
            validate_cron(cron)
            changes["cron"] = cron
        if enabled is not None:
            changes["enabled"] = enabled
        if retention is not None:
            if retention < 1:
                raise ValidationError("Keep one backup or more.")
            changes["retention"] = retention
        if rclone_remote is not None:
            changes["rclone_remote"] = rclone_remote or None

        self.config = self.config.replace(**changes)

        if self._scheduler is not None:
            self._scheduler.shutdown(wait=False)
            self._scheduler = None
        self.start()
        self._write_state()
        return self.config

    # -- running -----------------------------------------------------------

    async def run_now(self) -> BackupRun:
        """Write one backup, apply the retention rule, and push it if asked."""
        async with self._lock:
            started = datetime.now(UTC)
            destination = self.config.backup_dir / export_filename(
                BACKUP_PREFIX, started
            )
            try:
                self.config.backup_dir.mkdir(parents=True, exist_ok=True)
                result = await self._export(destination)
            except Exception as exc:
                logger.exception("The backup failed.")
                run = BackupRun(
                    started_at=started,
                    finished_at=datetime.now(UTC),
                    ok=False,
                    error=str(exc),
                )
                self._remember(run)
                return run

            pushed: str | None = None
            warnings = list(result.warnings)
            if self.config.rclone_remote:
                error = await push_with_rclone(result.path, self.config.rclone_remote)
                if error:
                    warnings.append(error)
                else:
                    pushed = self.config.rclone_remote

            deleted = self.apply_retention()
            run = BackupRun(
                started_at=started,
                finished_at=datetime.now(UTC),
                ok=True,
                path=result.path,
                size_bytes=result.size_bytes,
                pushed_to=pushed,
                deleted=deleted,
                warnings=tuple(warnings),
            )
            self._remember(run)
            return run

    async def _run_scheduled(self) -> None:
        """The job that APScheduler calls."""
        run = await self.run_now()
        if run.ok:
            logger.info("The scheduled backup wrote %s.", run.path)
        else:
            logger.error("The scheduled backup failed: %s", run.error)

    # -- files -------------------------------------------------------------

    def list_backups(self) -> list[dict[str, Any]]:
        """Return every backup file, newest first."""
        directory = self.config.backup_dir
        if not directory.exists():
            return []
        files = [
            path for path in directory.glob(f"{BACKUP_PREFIX}-*.zip") if path.is_file()
        ]
        files.sort(key=lambda path: path.stat().st_mtime, reverse=True)
        return [
            {
                "filename": path.name,
                "size_bytes": path.stat().st_size,
                "created_at": datetime.fromtimestamp(
                    path.stat().st_mtime, tz=UTC
                ).isoformat(),
            }
            for path in files
        ]

    def apply_retention(self) -> tuple[str, ...]:
        """Delete the oldest files above the retention count."""
        keep = max(1, self.config.retention)
        backups = self.list_backups()
        deleted: list[str] = []
        for entry in backups[keep:]:
            path = self.config.backup_dir / str(entry["filename"])
            try:
                path.unlink()
                deleted.append(path.name)
            except OSError as exc:
                logger.warning("The old backup %s stayed: %s", path, exc)
        return tuple(deleted)

    # -- status ------------------------------------------------------------

    def status(self) -> dict[str, Any]:
        """Return the answer of `GET /api/backup/status`."""
        next_run: str | None = None
        if self._scheduler is not None:
            jobs = self._scheduler.get_jobs()
            if jobs and jobs[0].next_run_time:
                next_run = jobs[0].next_run_time.isoformat()

        last = self._last_run.to_dict() if self._last_run else self._read_state()
        return {
            "enabled": self.config.enabled,
            "cron": self.config.cron,
            "retention": self.config.retention,
            "backup_dir": str(self.config.backup_dir),
            "rclone_remote": self.config.rclone_remote,
            "rclone_available": shutil.which("rclone") is not None,
            "running": self._scheduler is not None,
            "next_run_at": next_run,
            "last_run": last,
            "backups": self.list_backups(),
        }

    # -- internals ---------------------------------------------------------

    def _build_scheduler(self, cron: str) -> Any:
        """Create the APScheduler instance and add the backup job."""
        try:
            from apscheduler.schedulers.asyncio import AsyncIOScheduler
            from apscheduler.triggers.cron import CronTrigger
        except ImportError as exc:  # pragma: no cover
            raise BackupError("APScheduler is not installed.") from exc

        trigger = CronTrigger.from_crontab(cron, timezone=self.config.timezone or None)
        scheduler = AsyncIOScheduler(timezone=self.config.timezone or None)
        scheduler.add_job(
            self._run_scheduled,
            trigger=trigger,
            id="homestock-backup",
            name="HomeStock scheduled backup",
            replace_existing=True,
            coalesce=True,
            max_instances=1,
            misfire_grace_time=3600,
        )
        return scheduler

    def _remember(self, run: BackupRun) -> None:
        """Keep the last run in memory and on disk."""
        self._last_run = run
        self._write_state()

    @property
    def _state_path(self) -> Path:
        """Return the path of the state file."""
        return self.config.config_dir / STATE_FILENAME

    def _write_state(self) -> None:
        """Write the schedule and the last run to disk."""
        payload = {
            "enabled": self.config.enabled,
            "cron": self.config.cron,
            "retention": self.config.retention,
            "rclone_remote": self.config.rclone_remote,
            "last_run": self._last_run.to_dict() if self._last_run else None,
        }
        try:
            self.config.config_dir.mkdir(parents=True, exist_ok=True)
            self._state_path.write_text(json.dumps(payload, indent=2))
        except OSError as exc:
            logger.warning("The backup state file could not be written: %s", exc)

    def _read_state(self) -> dict[str, Any] | None:
        """Read the last run of an earlier container start."""
        try:
            payload = json.loads(self._state_path.read_text())
        except (OSError, json.JSONDecodeError):
            return None
        last = payload.get("last_run")
        return last if isinstance(last, dict) else None

    def load_state(self) -> None:
        """Apply the stored schedule, so a restart keeps the user's choice."""
        try:
            payload = json.loads(self._state_path.read_text())
        except (OSError, json.JSONDecodeError):
            return
        changes: dict[str, Any] = {}
        if isinstance(payload.get("cron"), str):
            try:
                validate_cron(payload["cron"])
                changes["cron"] = payload["cron"]
            except ValidationError:
                pass
        if isinstance(payload.get("enabled"), bool):
            changes["enabled"] = payload["enabled"]
        if isinstance(payload.get("retention"), int) and payload["retention"] > 0:
            changes["retention"] = payload["retention"]
        if isinstance(payload.get("rclone_remote"), str):
            changes["rclone_remote"] = payload["rclone_remote"] or None
        if changes:
            self.config = self.config.replace(**changes)


def validate_cron(expression: str) -> None:
    """Raise `ValidationError` if the cron expression is not usable."""
    try:
        from apscheduler.triggers.cron import CronTrigger

        CronTrigger.from_crontab(expression)
    except ImportError:  # pragma: no cover
        return
    except Exception as exc:
        raise ValidationError(
            f"'{expression}' is not a cron expression: {exc}"
        ) from exc


async def push_with_rclone(
    path: Path, remote: str, *, seconds: float = RCLONE_TIMEOUT
) -> str | None:
    """Copy one file to an rclone remote. Return a warning text on failure."""
    if shutil.which("rclone") is None:
        return "rclone is not installed, so the backup stayed on this server."
    try:
        process = await asyncio.create_subprocess_exec(
            "rclone",
            "copy",
            "--no-traverse",
            str(path),
            remote,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await asyncio.wait_for(process.communicate(), timeout=seconds)
    except TimeoutError:
        return f"rclone did not finish in {seconds:.0f} seconds."
    except OSError as exc:
        return f"rclone could not start: {exc}"

    if process.returncode != 0:
        return f"rclone failed: {stderr.decode('utf-8', 'replace').strip()[:300]}"
    return None


# --------------------------------------------------------------------------
# The default export callback
# --------------------------------------------------------------------------


async def write_installation_backup(destination: Path) -> ExportResult:
    """Write one full archive of the whole installation to `destination`.

    This is the callback that the scheduler runs. It archives every account,
    because a backup belongs to the server, not to one user.
    """
    from app.config import settings
    from app.database import SessionLocal
    from app.services.export_service import (
        FullExportRequest,
        build_full_export,
        items_to_csv,
    )
    from app.utils.queries import item_export_rows

    async with SessionLocal() as session:
        rows = await item_export_rows(session)

    return await build_full_export(
        FullExportRequest(
            destination=destination,
            metadata={"application": "HomeStock", "item_count": len(rows)},
            csv_bytes=items_to_csv(rows),
            database_url=settings.sync_database_url,
            uploads_dir=settings.upload_dir,
        )
    )


_service: BackupService | None = None


def get_backup_service() -> BackupService:
    """Return the process wide backup service.

    The scheduler lives on this object, so every caller must get the same
    instance. `main.py` starts it, and the backup routes read and change it.
    """
    global _service
    if _service is None:
        _service = BackupService(write_installation_backup)
        _service.load_state()
    return _service


__all__ = [
    "BACKUP_PREFIX",
    "BackupConfig",
    "BackupRun",
    "BackupService",
    "ExportCallback",
    "get_backup_service",
    "push_with_rclone",
    "validate_cron",
    "write_installation_backup",
]
