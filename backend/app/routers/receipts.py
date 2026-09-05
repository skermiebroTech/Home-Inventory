"""Receipt routes."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, File, Query, UploadFile, status

from app.schemas.common import Envelope, Message, Page
from app.schemas.receipt import ReceiptDetail, ReceiptRead, ReceiptUpdate
from app.utils.auth import CurrentUser, SessionDep
from app.utils.errors import not_implemented

router = APIRouter(prefix="/api/receipts", tags=["Receipts"])


@router.post(
    "/upload",
    response_model=Envelope[ReceiptDetail],
    status_code=status.HTTP_201_CREATED,
    summary="Upload a receipt image and start the OCR.",
    description=(
        "The row is created at once. The OCR runs on the CPU and may take a "
        "while, so ocr_parsed_json is null until it finishes. Poll the "
        "returned AI job, or fetch the receipt again."
    ),
)
async def upload_receipt(
    user: CurrentUser,
    session: SessionDep,
    file: Annotated[UploadFile, File(description="One image of a receipt.")],
) -> Envelope[ReceiptDetail]:
    not_implemented("POST /api/receipts/upload")


@router.get(
    "", response_model=Envelope[Page[ReceiptRead]], summary="List receipts."
)
async def list_receipts(
    user: CurrentUser,
    session: SessionDep,
    vendor: str | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    per_page: Annotated[int, Query(ge=1, le=200)] = 50,
) -> Envelope[Page[ReceiptRead]]:
    not_implemented("GET /api/receipts")


@router.get(
    "/{receipt_id}",
    response_model=Envelope[ReceiptDetail],
    summary="Return one receipt with its OCR output and its lines.",
)
async def get_receipt(
    receipt_id: uuid.UUID, user: CurrentUser, session: SessionDep
) -> Envelope[ReceiptDetail]:
    not_implemented("GET /api/receipts/{receipt_id}")


@router.put(
    "/{receipt_id}",
    response_model=Envelope[ReceiptDetail],
    summary="Correct the data that the OCR read.",
)
async def update_receipt(
    receipt_id: uuid.UUID,
    body: ReceiptUpdate,
    user: CurrentUser,
    session: SessionDep,
) -> Envelope[ReceiptDetail]:
    not_implemented("PUT /api/receipts/{receipt_id}")


@router.post(
    "/{receipt_id}/link/{item_id}",
    response_model=Envelope[ReceiptDetail],
    summary="Link a receipt line to an inventory item.",
)
async def link_receipt_item(
    receipt_id: uuid.UUID,
    item_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
    line_id: Annotated[
        uuid.UUID | None,
        Query(description="The receipt line to link. Omit to link the whole receipt."),
    ] = None,
) -> Envelope[ReceiptDetail]:
    not_implemented("POST /api/receipts/{receipt_id}/link/{item_id}")


@router.delete(
    "/{receipt_id}", response_model=Envelope[Message], summary="Delete a receipt."
)
async def delete_receipt(
    receipt_id: uuid.UUID, user: CurrentUser, session: SessionDep
) -> Envelope[Message]:
    not_implemented("DELETE /api/receipts/{receipt_id}")
