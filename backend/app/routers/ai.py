"""AI routes.

This server has no GPU. Every model runs on the CPU, so one image can take
tens of seconds. A plain synchronous request would outlive the reverse proxy
timeout and fail for the client.

Every AI route therefore returns an ``AiJob``:

* ``200`` when the model answered inside ``HS_AI_INLINE_TIMEOUT`` seconds.
  The job status is ``succeeded`` and the result is attached.
* ``202`` when it did not. The job status is ``queued`` or ``running``, and
  the client polls ``GET /api/ai/jobs/{job_id}`` until the status changes.

Both replies use the same shape, so a client needs only one code path.
"""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, File, Query, Response, UploadFile, status

from app.config import settings
from app.schemas.ai import (
    AiJob,
    AiJobKind,
    AiJobStatus,
    AiStatus,
    RecognizedItem,
    RecognizeResult,
)
from app.schemas.common import Envelope, ok
from app.schemas.receipt import ParsedReceipt, ParsedReceiptLine
from app.services.ai_service import AIService, RecognitionResult
from app.services.errors import AIUnavailableError
from app.services.job_service import JobRecord, get_job_store
from app.services.ocr_service import OCRService
from app.services.ocr_service import ParsedReceipt as ParsedReceiptData
from app.utils.auth import CurrentUser, SessionDep
from app.utils.errors import not_found, unavailable
from app.utils.queries import read_upload

router = APIRouter(prefix="/api/ai", tags=["AI"])

JOB_RESPONSES = {
    200: {"description": "The model finished inside the inline timeout."},
    202: {"description": "The work continues. Poll GET /api/ai/jobs/{job_id}."},
    503: {"description": "Ollama is unreachable, or HS_AI_ENABLED is false."},
}


# --------------------------------------------------------------------------
# Mapping the service results onto the API schemas
# --------------------------------------------------------------------------


def _recognize_result(result: RecognitionResult) -> RecognizeResult:
    """Turn the service result into the API shape."""
    return RecognizeResult(
        items=[
            RecognizedItem(
                name=suggestion.name,
                brand=suggestion.brand,
                category=suggestion.category,
                subcategory=suggestion.subcategory,
                estimated_value_aud=suggestion.estimated_value_aud,
                condition=suggestion.condition,
                region=list(suggestion.region) if suggestion.region else None,
            )
            for suggestion in result.suggestions
        ],
        model=result.model,
        duration_ms=result.duration_ms,
    )


def _receipt_result(parsed: ParsedReceiptData) -> ParsedReceipt:
    """Turn the parsed receipt into the API shape."""
    return ParsedReceipt(
        store_name=parsed.store_name,
        date=parsed.purchase_date,
        items=[
            ParsedReceiptLine(
                name=line.name,
                quantity=line.quantity,
                unit_price=line.unit_price,
                total=line.total,
            )
            for line in parsed.lines
        ],
        subtotal=parsed.subtotal,
        tax=parsed.tax,
        grand_total=parsed.grand_total,
        currency=parsed.currency,
    )


def _to_schema(job: JobRecord) -> AiJob:
    """Turn a job record into the API shape."""
    payload = AiJob(
        id=job.id,
        kind=AiJobKind(job.kind),
        status=AiJobStatus(job.status),
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
        error=job.error,
    )
    if job.status == AiJobStatus.SUCCEEDED:
        if isinstance(job.result, RecognitionResult):
            payload.recognize_result = _recognize_result(job.result)
        elif isinstance(job.result, ParsedReceiptData):
            payload.receipt_result = _receipt_result(job.result)
    return payload


# --------------------------------------------------------------------------
# Running one job
# --------------------------------------------------------------------------


def _guard_enabled() -> None:
    """Refuse an AI request when the operator turned the feature off."""
    if not settings.ai_enabled:
        raise unavailable(
            "ai_disabled",
            "The AI features are off. Set HS_AI_ENABLED to true to use them.",
        )


async def _run_job(
    *,
    kind: AiJobKind,
    work: Any,
    user_id: uuid.UUID,
    response: Response,
    wait: bool,
) -> Envelope[AiJob]:
    """Start one job, wait for the inline timeout, and shape the reply."""
    _guard_enabled()
    store = get_job_store()
    job = store.submit(kind=kind.value, user_id=user_id, work=work)

    timeout = float(settings.ai_inline_timeout) if wait else 0.0
    await store.wait(job, timeout)

    if job.status == AiJobStatus.FAILED and isinstance(
        job.exception, AIUnavailableError
    ):
        # Ollama is down. That is a 503, not a finished job with an error.
        raise unavailable(job.exception.code, job.exception.message)

    response.status_code = status.HTTP_200_OK if job.done else status.HTTP_202_ACCEPTED
    return ok(_to_schema(job))


@router.post(
    "/recognize",
    response_model=Envelope[AiJob],
    responses=JOB_RESPONSES,
    summary="Identify the item in a photograph.",
)
async def recognize(
    user: CurrentUser,
    session: SessionDep,
    response: Response,
    file: Annotated[UploadFile, File(description="One image of one item.")],
    wait: Annotated[
        bool,
        Query(description="Set false to return a job at once and never wait."),
    ] = True,
) -> Envelope[AiJob]:
    image = await read_upload(file)
    service = AIService()
    return await _run_job(
        kind=AiJobKind.RECOGNIZE,
        work=lambda: service.recognize(image),
        user_id=user.id,
        response=response,
        wait=wait,
    )


@router.post(
    "/bulk-scan",
    response_model=Envelope[AiJob],
    responses=JOB_RESPONSES,
    summary="Identify every item in a photograph of a shelf or a drawer.",
    description=(
        "A bulk scan is slower than a single recognize call. On a CPU it "
        "almost always returns 202."
    ),
)
async def bulk_scan(
    user: CurrentUser,
    session: SessionDep,
    response: Response,
    file: Annotated[UploadFile, File(description="One image of many items.")],
    wait: Annotated[bool, Query()] = True,
) -> Envelope[AiJob]:
    image = await read_upload(file)
    service = AIService()
    return await _run_job(
        kind=AiJobKind.BULK_SCAN,
        work=lambda: service.bulk_scan(image),
        user_id=user.id,
        response=response,
        wait=wait,
    )


@router.post(
    "/receipt-parse",
    response_model=Envelope[AiJob],
    responses=JOB_RESPONSES,
    summary="Read a receipt image and return structured data.",
    description=(
        "Tesseract extracts the text on the CPU, then the text model "
        "structures it. The vision model is not used here, because text "
        "inference on a CPU is much faster."
    ),
)
async def receipt_parse(
    user: CurrentUser,
    session: SessionDep,
    response: Response,
    file: Annotated[UploadFile, File(description="One image of a receipt.")],
    wait: Annotated[bool, Query()] = True,
) -> Envelope[AiJob]:
    image = await read_upload(file)
    service = OCRService()
    return await _run_job(
        kind=AiJobKind.RECEIPT_PARSE,
        work=lambda: service.parse(image),
        user_id=user.id,
        response=response,
        wait=wait,
    )


@router.get(
    "/jobs/{job_id}",
    response_model=Envelope[AiJob],
    summary="Poll one AI job.",
    description=(
        "This route is not in the original route list. CPU inference is too "
        "slow to answer inside one HTTP request, so the client polls here."
    ),
)
async def get_job(
    job_id: uuid.UUID, user: CurrentUser, session: SessionDep
) -> Envelope[AiJob]:
    job = get_job_store().get(job_id, user.id)
    if job is None:
        raise not_found("That AI job")
    return ok(_to_schema(job))


@router.get(
    "/status",
    response_model=Envelope[AiStatus],
    status_code=status.HTTP_200_OK,
    summary="Report whether the AI features can work.",
)
async def ai_status(user: CurrentUser, session: SessionDep) -> Envelope[AiStatus]:
    state = await AIService().status()
    message = state.error
    if state.available and not state.model_present:
        message = (
            f"Ollama is up, but it does not hold '{state.model}'. "
            f"Run: ollama pull {state.model}"
        )
    return ok(
        AiStatus(
            enabled=state.enabled,
            reachable=state.available,
            base_url=state.base_url,
            vision_model=state.model,
            text_model=state.text_model,
            models_installed=list(state.models),
            vision_model_installed=state.model_present,
            text_model_installed=state.text_model_present,
            # This deployment has no GPU. The field stays false unless Ollama
            # reports a model that is loaded into video memory.
            gpu_available=bool(state.gpu),
            inline_timeout_seconds=settings.ai_inline_timeout,
            message=message,
        )
    )
