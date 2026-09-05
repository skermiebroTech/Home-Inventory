"""Health and status schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ComponentHealth(BaseModel):
    """The state of one dependency."""

    ok: bool
    detail: str | None = None
    latency_ms: int | None = None


class DiskUsage(BaseModel):
    """Free space on the data volume."""

    path: str
    total_bytes: int
    used_bytes: int
    free_bytes: int
    percent_used: float


class HealthStatus(BaseModel):
    """The reply from GET /api/health.

    The Unraid Docker page and the Compose healthcheck both read this.
    """

    status: str = Field(description="ok, degraded, or error.")
    version: str
    database: ComponentHealth
    ollama: ComponentHealth
    disk: DiskUsage | None = None
    secret_key_is_default: bool = Field(
        description="True when the operator did not change HS_SECRET_KEY."
    )
    setup_required: bool = Field(
        description="True when no user account exists yet."
    )
