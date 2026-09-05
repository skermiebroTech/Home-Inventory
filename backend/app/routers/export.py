"""Export routes.

These routes return files, not the JSON envelope.
"""

from __future__ import annotations

import tempfile
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Query
from fastapi.responses import FileResponse, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.background import BackgroundTask

from app.config import settings
from app.models.item import Item
from app.models.location import Location
from app.models.maintenance import MaintenanceLog
from app.models.receipt import Receipt
from app.models.user import User
from app.services.errors import ServiceError, to_api_error
from app.services.export_service import (
    FullExportRequest,
    InsuranceReportOptions,
    build_full_export,
    build_insurance_pdf,
    export_filename,
    items_to_csv,
)
from app.utils.auth import CurrentUser, SessionDep
from app.utils.queries import item_export_rows

router = APIRouter(prefix="/api/export", tags=["Export"])


def _attachment(filename: str) -> dict[str, str]:
    """Return the header that makes a browser save the file."""
    return {"Content-Disposition": f'attachment; filename="{filename}"'}


@router.get(
    "/full",
    responses={
        200: {
            "content": {"application/zip": {}},
            "description": (
                "A ZIP that holds database.sql, the uploads directory, "
                "metadata.json, and inventory-report.csv."
            ),
        }
    },
    response_class=Response,
    summary="Download a full backup archive.",
)
async def export_full(user: CurrentUser, session: SessionDep) -> Response:
    rows = await item_export_rows(session, user)
    counts = await _counts(session, user)
    destination = Path(tempfile.mkdtemp(prefix="homestock-export-")) / export_filename()

    try:
        result = await build_full_export(
            FullExportRequest(
                destination=destination,
                metadata={
                    "application": "HomeStock",
                    "exported_by": user.email,
                    **counts,
                },
                csv_bytes=items_to_csv(rows),
                database_url=settings.sync_database_url,
                uploads_dir=settings.upload_dir,
            )
        )
    except ServiceError as exc:
        raise to_api_error(exc) from exc

    return FileResponse(
        result.path,
        media_type="application/zip",
        filename=result.path.name,
        headers={"X-Export-Warnings": "; ".join(result.warnings)[:400]}
        if result.warnings
        else None,
        # The temporary directory goes away once the client has the bytes.
        background=BackgroundTask(_cleanup, result.path),
    )


def _cleanup(path: Path) -> None:
    """Delete the temporary export once the reply is sent."""
    import shutil

    shutil.rmtree(path.parent, ignore_errors=True)


async def _counts(session: AsyncSession, user: User) -> dict[str, int]:
    """Count the rows that go into the export metadata."""

    async def total(model: Any) -> int:
        statement = select(func.count()).select_from(model)
        if hasattr(model, "user_id"):
            statement = statement.where(model.user_id == user.id)
        if hasattr(model, "deleted_at"):
            statement = statement.where(model.deleted_at.is_(None))
        return int(await session.scalar(statement) or 0)

    return {
        "item_count": await total(Item),
        "location_count": await total(Location),
        "receipt_count": await total(Receipt),
        "maintenance_count": await total(MaintenanceLog),
    }


@router.get(
    "/csv",
    responses={200: {"content": {"text/csv": {}}, "description": "Every item as CSV."}},
    response_class=Response,
    summary="Download every item as a CSV file.",
)
async def export_csv(user: CurrentUser, session: SessionDep) -> Response:
    rows = await item_export_rows(session, user)
    stamp = datetime.now(UTC).strftime("%Y%m%d")
    return Response(
        content=items_to_csv(rows),
        media_type="text/csv; charset=utf-8",
        headers=_attachment(f"homestock-items-{stamp}.csv"),
    )


@router.get(
    "/insurance-report",
    responses={
        200: {
            "content": {"application/pdf": {}},
            "description": "A PDF report with photographs and values.",
        }
    },
    response_class=Response,
    summary="Generate an insurance report as a PDF.",
)
async def export_insurance_report(
    user: CurrentUser,
    session: SessionDep,
    include_photos: Annotated[bool, Query()] = True,
    min_value: Annotated[float | None, Query(ge=0)] = None,
) -> Response:
    rows: Sequence[dict[str, Any]] = await item_export_rows(
        session, user, min_value=min_value, with_photos=include_photos
    )
    try:
        pdf = await build_insurance_pdf(
            rows,
            options=InsuranceReportOptions(
                owner=user.name,
                include_photos=include_photos,
            ),
        )
    except ServiceError as exc:
        raise to_api_error(exc) from exc

    stamp = datetime.now(UTC).strftime("%Y%m%d")
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers=_attachment(f"homestock-insurance-{stamp}.pdf"),
    )
