"""Health and dashboard routes.

The health route is the only route that Phase 1 implements. The Compose
healthcheck and the Unraid Docker page both read it, so it must work before
any business logic exists.
"""

from __future__ import annotations

import shutil
import time
from datetime import date, timedelta
from decimal import Decimal

import httpx
from fastapi import APIRouter, Response, status
from sqlalchemy import func, select, text

from app import __version__
from app.config import settings
from app.models.item import Item
from app.models.location import Location
from app.models.maintenance import MaintenanceLog
from app.models.receipt import Receipt
from app.models.user import User
from app.schemas.common import Envelope, ok
from app.schemas.dashboard import DashboardSummary, LocationCount
from app.schemas.health import ComponentHealth, DiskUsage, HealthStatus
from app.utils.auth import CurrentUser, SessionDep

router = APIRouter(prefix="/api", tags=["Health"])

#: The dashboard counts maintenance and warranties inside this window.
DASHBOARD_HORIZON_DAYS = 30


async def _check_database(session: SessionDep) -> tuple[ComponentHealth, bool]:
    """Return the database health, and whether a user account exists."""
    start = time.perf_counter()
    try:
        await session.execute(text("SELECT 1"))
    except Exception as exc:
        return (
            ComponentHealth(ok=False, detail=f"{type(exc).__name__}: {exc}"),
            False,
        )
    latency = int((time.perf_counter() - start) * 1000)

    # The table is missing until Alembic has run. That is not a failure.
    try:
        count = await session.scalar(select(func.count()).select_from(User))
        has_user = bool(count)
        detail = None
    except Exception:
        await session.rollback()
        has_user = False
        detail = "Connected, but the schema is not migrated yet."

    return ComponentHealth(ok=True, detail=detail, latency_ms=latency), has_user


async def _check_ollama() -> ComponentHealth:
    """Ask Ollama for its model list."""
    if not settings.ai_enabled:
        return ComponentHealth(ok=False, detail="HS_AI_ENABLED is false.")
    start = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(f"{settings.ollama_url.rstrip('/')}/api/tags")
            response.raise_for_status()
    except Exception as exc:
        return ComponentHealth(ok=False, detail=f"{type(exc).__name__}: {exc}")
    latency = int((time.perf_counter() - start) * 1000)
    return ComponentHealth(ok=True, latency_ms=latency)


def _check_disk() -> DiskUsage | None:
    """Measure free space on the data volume."""
    try:
        usage = shutil.disk_usage(settings.data_dir)
    except OSError:
        return None
    percent = (usage.used / usage.total * 100) if usage.total else 0.0
    return DiskUsage(
        path=str(settings.data_dir),
        total_bytes=usage.total,
        used_bytes=usage.used,
        free_bytes=usage.free,
        percent_used=round(percent, 2),
    )


@router.get(
    "/health",
    response_model=Envelope[HealthStatus],
    summary="Report the state of the service and its dependencies.",
    description=(
        "The status is ``ok`` when the database answers and the AI is "
        "reachable, ``degraded`` when only the AI is down, and ``error`` "
        "when the database is down. The Compose healthcheck treats "
        "``degraded`` as healthy, because the AI is optional."
    ),
)
async def health(session: SessionDep, response: Response) -> Envelope[HealthStatus]:
    database, has_user = await _check_database(session)
    ollama = await _check_ollama()

    if not database.ok:
        status_text = "error"
        # The Compose healthcheck and the Unraid Docker page both watch the
        # HTTP status. A body that says "error" under a 200 reply would keep
        # the container marked healthy while it cannot serve a single request.
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    elif not ollama.ok:
        # The AI is optional. The service still works without it, so this
        # stays a 200 reply.
        status_text = "degraded"
    else:
        status_text = "ok"

    return ok(
        HealthStatus(
            status=status_text,
            version=__version__,
            database=database,
            ollama=ollama,
            disk=_check_disk(),
            secret_key_is_default=settings.secret_key_is_default,
            setup_required=not has_user,
        )
    )


@router.get(
    "/dashboard",
    response_model=Envelope[DashboardSummary],
    tags=["Dashboard"],
    summary="Return the totals for the dashboard page.",
    description=(
        "This route is not in the original route list. The dashboard needs "
        "seven counts, and one aggregate query is cheaper than seven list "
        "calls from the browser."
    ),
)
async def dashboard(
    user: CurrentUser, session: SessionDep
) -> Envelope[DashboardSummary]:
    today = date.today()
    horizon = today + timedelta(days=DASHBOARD_HORIZON_DAYS)
    live_items = (Item.user_id == user.id, Item.deleted_at.is_(None))

    totals = (
        await session.execute(
            select(
                func.count(Item.id),
                func.coalesce(func.sum(Item.quantity), 0),
                func.coalesce(
                    func.sum(
                        func.coalesce(Item.current_value, Item.purchase_price, 0)
                        * Item.quantity
                    ),
                    0,
                ),
            ).where(*live_items)
        )
    ).one()

    by_location = (
        await session.execute(
            select(
                Location.id,
                Location.name,
                func.count(Item.id),
                func.coalesce(
                    func.sum(
                        func.coalesce(Item.current_value, Item.purchase_price, 0)
                        * Item.quantity
                    ),
                    0,
                ),
            )
            .join(Item, Item.location_id == Location.id)
            .where(*live_items, Location.deleted_at.is_(None))
            .group_by(Location.id, Location.name)
            .order_by(func.count(Item.id).desc())
        )
    ).all()

    lent_count = await session.scalar(
        select(func.count(Item.id)).where(*live_items, Item.is_lent.is_(True))
    )
    maintenance_due = await session.scalar(
        select(func.count(MaintenanceLog.id))
        .join(Item, Item.id == MaintenanceLog.item_id)
        .where(
            *live_items,
            MaintenanceLog.deleted_at.is_(None),
            MaintenanceLog.next_due_date.is_not(None),
            MaintenanceLog.next_due_date <= horizon,
        )
    )
    warranty_expiring = await session.scalar(
        select(func.count(Item.id)).where(
            *live_items,
            Item.warranty_expires.is_not(None),
            Item.warranty_expires >= today,
            Item.warranty_expires <= horizon,
        )
    )
    receipt_count = await session.scalar(
        select(func.count(Receipt.id)).where(
            Receipt.user_id == user.id, Receipt.deleted_at.is_(None)
        )
    )

    return ok(
        DashboardSummary(
            total_items=int(totals[0] or 0),
            total_quantity=int(totals[1] or 0),
            total_value=Decimal(str(totals[2] or 0)),
            items_by_location=[
                LocationCount(
                    location_id=row[0],
                    location_name=row[1],
                    item_count=int(row[2]),
                    total_value=Decimal(str(row[3] or 0)),
                )
                for row in by_location
            ],
            lent_count=int(lent_count or 0),
            maintenance_due_count=int(maintenance_due or 0),
            warranty_expiring_count=int(warranty_expiring or 0),
            receipt_count=int(receipt_count or 0),
        )
    )
