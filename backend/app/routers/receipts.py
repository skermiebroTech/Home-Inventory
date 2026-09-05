"""Receipt routes."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, File, Query, Response, UploadFile, status
from sqlalchemy import select

from app.database import SessionLocal
from app.models.receipt import Receipt, ReceiptItem
from app.schemas.common import Envelope, Message, Page, ok
from app.schemas.receipt import ReceiptDetail, ReceiptRead, ReceiptUpdate
from app.services.job_service import get_job_store
from app.services.ocr_service import DEFAULT_CURRENCY, OCRService, ParsedReceipt
from app.utils.auth import CurrentUser, SessionDep
from app.utils.errors import ApiError, not_found
from app.utils.queries import (
    build_page,
    get_item_or_404,
    get_receipt_or_404,
    paginate,
    read_upload,
)
from app.utils.thumbnails import (
    UnsupportedImageError,
    delete_image_set,
    store_image,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/receipts", tags=["Receipts"])


async def _detail(session: SessionDep, receipt: Receipt) -> ReceiptDetail:
    """Build the detail shape, with the receipt lines loaded."""
    await session.refresh(receipt)
    await session.refresh(receipt, ["lines"])
    return ReceiptDetail.model_validate(receipt)


async def _parse_in_background(receipt_id: uuid.UUID, image: bytes) -> ParsedReceipt:
    """Read the receipt and write the result onto the row.

    This runs after the upload reply is already sent, in its own session,
    because the request session closes with the request.
    """
    parsed = await OCRService().parse(image)
    async with SessionLocal() as session:
        receipt = await session.get(Receipt, receipt_id)
        if receipt is None:
            return parsed

        columns = parsed.to_receipt_columns()
        receipt.vendor = columns["vendor"]
        receipt.purchase_date = columns["purchase_date"]
        receipt.total_amount = (
            Decimal(str(columns["total_amount"]))
            if columns["total_amount"] is not None
            else None
        )
        receipt.currency = columns["currency"] or DEFAULT_CURRENCY
        receipt.ocr_raw_text = columns["ocr_raw_text"]
        receipt.ocr_parsed_json = parsed.to_dict()
        receipt.version += 1

        for line in parsed.lines:
            session.add(
                ReceiptItem(
                    receipt_id=receipt.id,
                    line_text=line.name,
                    line_amount=(
                        Decimal(str(line.total)) if line.total is not None else None
                    ),
                )
            )
        await session.commit()
    return parsed


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
    response: Response,
    file: Annotated[UploadFile, File(description="One image of a receipt.")],
) -> Envelope[ReceiptDetail]:
    data = await read_upload(file)

    receipt = Receipt(user_id=user.id, file_path="", currency=DEFAULT_CURRENCY)
    session.add(receipt)
    await session.flush()

    try:
        stored = await store_image(data, kind="receipts", entity_id=receipt.id)
    except UnsupportedImageError as exc:
        await session.rollback()
        raise ApiError(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "bad_image", str(exc)
        ) from exc

    receipt.file_path = stored.relative_original
    if stored.thumbnails:
        receipt.thumbnail_path = stored.relative_thumbnails[min(stored.thumbnails)]
    await session.commit()

    # The OCR and the model call are slow on a CPU, so they run after the
    # reply. The job id goes in a header for a client that wants to poll it.
    #
    # The id is read here, not inside the task. The task starts at the next
    # await, which is the refresh below, and an ORM attribute read during a
    # refresh would be a second operation on the same session.
    receipt_id = receipt.id
    job = get_job_store().submit(
        kind="receipt_parse",
        user_id=user.id,
        work=lambda: _parse_in_background(receipt_id, data),
    )
    response.headers["X-AI-Job-Id"] = str(job.id)
    return ok(await _detail(session, receipt))


@router.get("", response_model=Envelope[Page[ReceiptRead]], summary="List receipts.")
async def list_receipts(
    user: CurrentUser,
    session: SessionDep,
    vendor: str | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    per_page: Annotated[int, Query(ge=1, le=200)] = 50,
) -> Envelope[Page[ReceiptRead]]:
    statement = select(Receipt).where(
        Receipt.user_id == user.id, Receipt.deleted_at.is_(None)
    )
    if vendor:
        statement = statement.where(Receipt.vendor.ilike(f"%{vendor.strip()}%"))
    statement = statement.order_by(
        Receipt.purchase_date.desc().nullslast(), Receipt.created_at.desc()
    )

    rows, total, pages = await paginate(
        session, statement, page=page, per_page=per_page
    )
    return ok(
        build_page(
            [ReceiptRead.model_validate(row) for row in rows],
            total,
            page,
            per_page,
            pages,
        )
    )


@router.get(
    "/{receipt_id}",
    response_model=Envelope[ReceiptDetail],
    summary="Return one receipt with its OCR output and its lines.",
)
async def get_receipt(
    receipt_id: uuid.UUID, user: CurrentUser, session: SessionDep
) -> Envelope[ReceiptDetail]:
    receipt = await get_receipt_or_404(session, receipt_id, user, with_lines=True)
    return ok(ReceiptDetail.model_validate(receipt))


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
    receipt = await get_receipt_or_404(session, receipt_id, user, with_lines=True)
    for field, value in body.model_dump(exclude_unset=True).items():
        if field == "currency" and value:
            value = value.upper()
        setattr(receipt, field, value)
    receipt.version += 1
    await session.commit()
    return ok(await _detail(session, receipt))


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
    receipt = await get_receipt_or_404(session, receipt_id, user, with_lines=True)
    item = await get_item_or_404(session, item_id, user)

    if line_id is not None:
        line = next((entry for entry in receipt.lines if entry.id == line_id), None)
        if line is None:
            raise not_found("That receipt line")
        line.item_id = item.id
    elif not any(entry.item_id == item.id for entry in receipt.lines):
        # No line was named, so the whole receipt covers this item. A new line
        # records the link and keeps the purchase price beside it.
        session.add(
            ReceiptItem(
                receipt_id=receipt.id,
                item_id=item.id,
                line_text=item.name,
                line_amount=item.purchase_price,
            )
        )

    receipt.version += 1
    await session.commit()
    return ok(await _detail(session, receipt))


@router.delete(
    "/{receipt_id}", response_model=Envelope[Message], summary="Delete a receipt."
)
async def delete_receipt(
    receipt_id: uuid.UUID, user: CurrentUser, session: SessionDep
) -> Envelope[Message]:
    receipt = await get_receipt_or_404(session, receipt_id, user)
    if receipt.file_path:
        delete_image_set(receipt.file_path)
    receipt.deleted_at = datetime.now(UTC)
    receipt.version += 1
    await session.commit()
    return ok(Message(message="The receipt is deleted."))
