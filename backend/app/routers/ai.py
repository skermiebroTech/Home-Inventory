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
from typing import Annotated

from fastapi import APIRouter, File, Query, Response, UploadFile, status

from app.schemas.ai import AiJob, AiStatus
from app.schemas.common import Envelope
from app.utils.auth import CurrentUser, SessionDep
from app.utils.errors import not_implemented

router = APIRouter(prefix="/api/ai", tags=["AI"])

JOB_RESPONSES = {
    200: {"description": "The model finished inside the inline timeout."},
    202: {"description": "The work continues. Poll GET /api/ai/jobs/{job_id}."},
    503: {"description": "Ollama is unreachable, or HS_AI_ENABLED is false."},
}


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
    not_implemented("POST /api/ai/recognize")


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
    not_implemented("POST /api/ai/bulk-scan")


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
    not_implemented("POST /api/ai/receipt-parse")


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
    not_implemented("GET /api/ai/jobs/{job_id}")


@router.get(
    "/status",
    response_model=Envelope[AiStatus],
    status_code=status.HTTP_200_OK,
    summary="Report whether the AI features can work.",
)
async def ai_status(user: CurrentUser, session: SessionDep) -> Envelope[AiStatus]:
    not_implemented("GET /api/ai/status")
