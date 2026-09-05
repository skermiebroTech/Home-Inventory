"""A small in-memory job store for the AI routes.

The server has no GPU, so one image can take tens of seconds. A plain
synchronous request would outlive the reverse proxy timeout. Each AI route
therefore starts a job, waits a short time for it, and either returns the
finished result or hands the client a job id to poll.

The store lives in the process. A container restart loses the queued jobs,
which is acceptable: the client simply sends the image again.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Final

logger = logging.getLogger(__name__)

STATUS_QUEUED: Final[str] = "queued"
STATUS_RUNNING: Final[str] = "running"
STATUS_SUCCEEDED: Final[str] = "succeeded"
STATUS_FAILED: Final[str] = "failed"

#: How long a finished job stays readable.
DEFAULT_TTL_SECONDS: Final[int] = 1800
#: The largest number of jobs that the store holds.
DEFAULT_MAX_JOBS: Final[int] = 200


@dataclass
class JobRecord:
    """One unit of AI work."""

    id: uuid.UUID
    kind: str
    user_id: uuid.UUID
    status: str = STATUS_QUEUED
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error: str | None = None
    result: Any = None
    exception: BaseException | None = None
    task: asyncio.Task[Any] | None = None

    @property
    def done(self) -> bool:
        """Return True if the job will not change again."""
        return self.status in (STATUS_SUCCEEDED, STATUS_FAILED)


class JobStore:
    """Holds the running and the recently finished jobs."""

    def __init__(
        self,
        *,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
        max_jobs: int = DEFAULT_MAX_JOBS,
    ) -> None:
        self._jobs: dict[uuid.UUID, JobRecord] = {}
        self._ttl = timedelta(seconds=ttl_seconds)
        self._max_jobs = max_jobs

    def submit(
        self,
        *,
        kind: str,
        user_id: uuid.UUID,
        work: Callable[[], Awaitable[Any]],
    ) -> JobRecord:
        """Start one job and return its record at once."""
        self.prune()
        job = JobRecord(id=uuid.uuid4(), kind=kind, user_id=user_id)
        self._jobs[job.id] = job
        job.task = asyncio.create_task(self._run(job, work), name=f"ai-{kind}")
        return job

    async def _run(self, job: JobRecord, work: Callable[[], Awaitable[Any]]) -> None:
        """Run the work and record what happened."""
        job.status = STATUS_RUNNING
        job.started_at = datetime.now(UTC)
        try:
            job.result = await work()
            job.status = STATUS_SUCCEEDED
        except asyncio.CancelledError:
            job.status = STATUS_FAILED
            job.error = "The job was cancelled."
            raise
        except Exception as exc:  # the job must record every failure
            job.status = STATUS_FAILED
            job.error = str(exc)
            job.exception = exc
            logger.info("The AI job %s failed: %s", job.kind, exc)
        finally:
            job.finished_at = datetime.now(UTC)

    async def wait(self, job: JobRecord, timeout: float) -> JobRecord:
        """Wait a short time for a job. Return it whether it finished or not."""
        if job.task is None or job.done or timeout <= 0:
            return job
        try:
            await asyncio.wait_for(asyncio.shield(job.task), timeout=timeout)
        except TimeoutError:
            # The work continues in the background. The client polls for it.
            pass
        except Exception:  # noqa: S110 - _run already recorded the failure
            pass
        return job

    def get(self, job_id: uuid.UUID, user_id: uuid.UUID | None = None) -> JobRecord | None:
        """Return one job of this user, or None."""
        job = self._jobs.get(job_id)
        if job is None:
            return None
        if user_id is not None and job.user_id != user_id:
            return None
        return job

    def prune(self) -> None:
        """Drop the jobs that are finished and old."""
        now = datetime.now(UTC)
        stale = [
            job_id
            for job_id, job in self._jobs.items()
            if job.done and job.finished_at and now - job.finished_at > self._ttl
        ]
        for job_id in stale:
            del self._jobs[job_id]

        if len(self._jobs) <= self._max_jobs:
            return
        finished = sorted(
            (job for job in self._jobs.values() if job.done),
            key=lambda job: job.finished_at or job.created_at,
        )
        for job in finished[: len(self._jobs) - self._max_jobs]:
            self._jobs.pop(job.id, None)

    async def shutdown(self) -> None:
        """Cancel every running job. The lifespan handler calls this."""
        tasks = [job.task for job in self._jobs.values() if job.task and not job.task.done()]
        for task in tasks:
            task.cancel()
        for task in tasks:
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass
        self._jobs.clear()


_store: JobStore | None = None


def get_job_store() -> JobStore:
    """Return the process wide job store."""
    global _store
    if _store is None:
        _store = JobStore()
    return _store


__all__ = [
    "DEFAULT_MAX_JOBS",
    "DEFAULT_TTL_SECONDS",
    "STATUS_FAILED",
    "STATUS_QUEUED",
    "STATUS_RUNNING",
    "STATUS_SUCCEEDED",
    "JobRecord",
    "JobStore",
    "get_job_store",
]
