"""QR label routes.

These routes return a PNG image, not the JSON envelope. A browser and a print
dialog both need the raw bytes.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Query, Request
from fastapi.responses import Response

from app.utils.auth import CurrentUser, SessionDep
from app.utils.qr import render_label_png
from app.utils.queries import get_item_or_404, get_location_or_404

router = APIRouter(prefix="/api", tags=["Labels"])

PNG_RESPONSE = {
    200: {"content": {"image/png": {}}, "description": "A QR code as a PNG image."}
}

#: A printed label does not change, so a browser may hold it for a day.
CACHE_CONTROL = "private, max-age=86400"


def _base_url(request: Request) -> str:
    """Return the address that the client used to reach this server.

    The QR code holds that address, so a phone camera opens the web interface
    on the same host that printed the label.
    """
    return str(request.base_url).rstrip("/")


def _png(data: bytes, filename: str) -> Response:
    """Return PNG bytes with the headers that a print dialog needs."""
    return Response(
        content=data,
        media_type="image/png",
        headers={
            "Content-Disposition": f'inline; filename="{filename}"',
            "Cache-Control": CACHE_CONTROL,
        },
    )


@router.get(
    "/items/{item_id}/qr",
    responses=PNG_RESPONSE,
    response_class=Response,
    summary="Generate a QR code that opens this item.",
)
async def item_qr(
    item_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
    request: Request,
    size: Annotated[int, Query(ge=64, le=2048, description="Width in pixels.")] = 512,
) -> Response:
    item = await get_item_or_404(session, item_id, user)
    png = await render_label_png(
        "item",
        item.id,
        # The number goes under the code, so a person can read it out or
        # type it when the camera will not focus.
        caption=f"{item.asset_tag} · {item.name}",
        base_url=_base_url(request),
        width=size,
        asset_tag=item.asset_tag,
    )
    return _png(png, f"item-{item.id}.png")


@router.get(
    "/locations/{location_id}/qr",
    responses=PNG_RESPONSE,
    response_class=Response,
    summary="Generate a QR code that opens this location.",
)
async def location_qr(
    location_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
    request: Request,
    size: Annotated[int, Query(ge=64, le=2048, description="Width in pixels.")] = 512,
) -> Response:
    location = await get_location_or_404(session, location_id, user)
    png = await render_label_png(
        "location",
        location.id,
        caption=location.name,
        base_url=_base_url(request),
        width=size,
    )
    return _png(png, f"location-{location.id}.png")
