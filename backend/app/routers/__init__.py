"""FastAPI routers.

``ALL_ROUTERS`` fixes the registration order. FastAPI matches routes in the
order it registers them, so a router that owns a fixed path must come before
a router that owns a matching parametrised path. The lending router holds
``/api/items/lent``, which would otherwise be swallowed by
``/api/items/{item_id}``.
"""

from fastapi import APIRouter

from app.routers import (
    ai,
    auth,
    backup,
    cables,
    components,
    export,
    health,
    items,
    labels,
    lending,
    locations,
    maintenance,
    nfc,
    receipts,
    sync,
    tags,
)

ALL_ROUTERS: list[APIRouter] = [
    health.router,
    auth.router,
    lending.router,  # Must precede items: it owns /api/items/lent.
    maintenance.router,  # Owns /api/items/{item_id}/maintenance.
    labels.router,  # Owns /api/items/{item_id}/qr.
    components.router,  # Owns /api/items/{item_id}/components.
    items.router,
    locations.router,
    tags.router,
    cables.router,
    receipts.router,
    ai.router,
    nfc.router,
    export.router,
    backup.router,
    sync.router,
]

__all__ = ["ALL_ROUTERS"]
