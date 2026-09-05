"""Export routes.

These routes return files, not the JSON envelope.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query
from fastapi.responses import Response

from app.utils.auth import CurrentUser, SessionDep
from app.utils.errors import not_implemented

router = APIRouter(prefix="/api/export", tags=["Export"])


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
    not_implemented("GET /api/export/full")


@router.get(
    "/csv",
    responses={
        200: {"content": {"text/csv": {}}, "description": "Every item as CSV."}
    },
    response_class=Response,
    summary="Download every item as a CSV file.",
)
async def export_csv(user: CurrentUser, session: SessionDep) -> Response:
    not_implemented("GET /api/export/csv")


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
    not_implemented("GET /api/export/insurance-report")
