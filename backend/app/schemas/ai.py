"""AI schemas.

The server has no GPU. Every model runs on the CPU, so a single image can take
tens of seconds. A plain synchronous request would outlive the reverse proxy
timeout, so the AI routes use a job.

The client posts an image. If the model answers within
``HS_AI_INLINE_TIMEOUT`` seconds, the route returns 200 with the result
already attached. If it does not, the route returns 202 with the job in the
``running`` state, and the client polls ``GET /api/ai/jobs/{job_id}``.
Both replies use the same ``AiJob`` shape, so a client can handle one type.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field

from app.schemas.receipt import ParsedReceipt


class AiJobStatus(StrEnum):
    """Where a job is in its life."""

    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class AiJobKind(StrEnum):
    """What a job asked the model to do."""

    RECOGNIZE = "recognize"
    BULK_SCAN = "bulk_scan"
    RECEIPT_PARSE = "receipt_parse"


class RecognizedItem(BaseModel):
    """One item that the vision model found in a photograph."""

    name: str
    brand: str | None = None
    model: str | None = Field(
        default=None, description="Read from a label or a rating plate."
    )
    serial_number: str | None = Field(
        default=None, description="Only when the text of a photograph shows it."
    )
    category: str | None = None
    subcategory: str | None = None
    estimated_value_aud: Decimal | None = None
    condition: str | None = None
    confidence: float | None = Field(
        default=None,
        ge=0,
        le=1,
        description="The model's own confidence, if it reports one.",
    )
    region: list[int] | None = Field(
        default=None,
        min_length=4,
        max_length=4,
        description="A bounding box as [x, y, width, height], for a bulk scan.",
    )


class RecognizeResult(BaseModel):
    """The result of a recognize job or a bulk scan job."""

    items: list[RecognizedItem] = Field(default_factory=list)
    model: str
    duration_ms: int
    image_count: int = Field(
        default=1, description="How many photographs the model read."
    )
    ocr_text: str | None = Field(
        default=None,
        description="The text that OCR read from the photographs, if any.",
    )


class AiJob(BaseModel):
    """A unit of AI work, and its result when it is done."""

    id: uuid.UUID
    kind: AiJobKind
    status: AiJobStatus
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error: str | None = Field(default=None, description="Set when status is failed.")
    recognize_result: RecognizeResult | None = None
    receipt_result: ParsedReceipt | None = None


class AiStatus(BaseModel):
    """Whether the AI features can work right now."""

    enabled: bool = Field(description="False when HS_AI_ENABLED is off.")
    reachable: bool = Field(description="Whether Ollama answered.")
    base_url: str
    vision_model: str
    text_model: str
    models_installed: list[str] = Field(
        default_factory=list, description="Models that Ollama already holds."
    )
    vision_model_installed: bool = False
    text_model_installed: bool = False
    gpu_available: bool = Field(
        default=False,
        description="Always false on this deployment. Inference runs on the CPU.",
    )
    inline_timeout_seconds: int
    message: str | None = Field(
        default=None, description="Why the AI is unavailable, when it is."
    )
