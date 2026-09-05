"""Ollama integration: item recognition, bulk scan, and receipt parsing.

Every call degrades in a controlled way. If `HS_AI_ENABLED` is false, or if
Ollama does not answer, the service raises `AIUnavailableError` and the router
returns 503 with the standard envelope. `status()` never raises, so the health
check and the settings page always get an answer.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Final

import httpx

from app.services.errors import AIUnavailableError, UpstreamError
from app.utils.settings import setting

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------
# Prompts
# --------------------------------------------------------------------------

ITEM_RECOGNITION_PROMPT: Final[str] = (
    "You are a home inventory assistant. Analyze this image and identify every "
    "distinct item visible. For each item return a JSON array of objects with: "
    "name, brand (if visible, else null), category, subcategory, "
    "estimated_value_aud (number), condition (new/good/fair/poor). Be specific "
    "— say 'DeWalt DCD771 cordless drill' not just 'drill'."
)

BULK_SCAN_SUFFIX: Final[str] = (
    " This image shows a shelf, a drawer, or a work area that holds several "
    "items. List every item as its own object. Add a 'region' field to each "
    "object with the bounding box of the item in pixels, as the four numbers "
    "[x, y, width, height]."
)

RECEIPT_PARSE_PROMPT: Final[str] = (
    "Parse this receipt image. Return JSON with: store_name, date (YYYY-MM-DD), "
    "items (array of {name, quantity, unit_price, total}), subtotal, tax, "
    "grand_total, currency. If any field is unreadable, use null."
)

VALID_CONDITIONS: Final[frozenset[str]] = frozenset({"new", "good", "fair", "poor"})

#: Below this much OCR text, the image goes to the vision model instead.
MIN_OCR_TEXT_CHARS: Final[int] = 40

DEFAULT_BASE_URL: Final[str] = "http://ollama:11434"
DEFAULT_MODEL: Final[str] = "moondream"
DEFAULT_TEXT_MODEL: Final[str] = "llama3.2:3b"
DEFAULT_TIMEOUT: Final[float] = 300.0
#: The status check must stay fast, because the health route calls it.
STATUS_TIMEOUT: Final[float] = 5.0


# --------------------------------------------------------------------------
# Data
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class OllamaConfig:
    """Where Ollama is and which model to ask."""

    base_url: str = DEFAULT_BASE_URL
    model: str = DEFAULT_MODEL
    #: Receipt text goes to this model. Text inference on a CPU is several
    #: times faster than vision inference.
    text_model: str = DEFAULT_TEXT_MODEL
    timeout: float = DEFAULT_TIMEOUT
    enabled: bool = True

    @classmethod
    def from_settings(cls) -> OllamaConfig:
        """Build the configuration from the environment."""
        return cls(
            base_url=str(setting("ollama_url", DEFAULT_BASE_URL) or DEFAULT_BASE_URL),
            model=str(setting("ollama_vision_model", DEFAULT_MODEL) or DEFAULT_MODEL),
            text_model=str(
                setting("ollama_text_model", DEFAULT_TEXT_MODEL) or DEFAULT_TEXT_MODEL
            ),
            timeout=float(
                setting("ollama_timeout", DEFAULT_TIMEOUT) or DEFAULT_TIMEOUT
            ),
            enabled=bool(setting("ai_enabled", True)),
        )


@dataclass(frozen=True, slots=True)
class AIStatus:
    """The answer of `GET /api/ai/status` and part of the health check."""

    enabled: bool
    available: bool
    base_url: str
    model: str
    text_model: str = DEFAULT_TEXT_MODEL
    model_present: bool = False
    text_model_present: bool = False
    models: tuple[str, ...] = ()
    version: str | None = None
    gpu: bool | None = None
    loaded_models: tuple[str, ...] = ()
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Return the status as a plain dictionary."""
        return {
            "enabled": self.enabled,
            "available": self.available,
            "base_url": self.base_url,
            "model": self.model,
            "text_model": self.text_model,
            "model_present": self.model_present,
            "text_model_present": self.text_model_present,
            "models": list(self.models),
            "version": self.version,
            "gpu": self.gpu,
            "loaded_models": list(self.loaded_models),
            "error": self.error,
        }


@dataclass(frozen=True, slots=True)
class ItemSuggestion:
    """One item that the vision model found in a photograph."""

    name: str
    brand: str | None = None
    category: str | None = None
    subcategory: str | None = None
    estimated_value_aud: float | None = None
    condition: str | None = None
    region: tuple[int, int, int, int] | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    def to_item_payload(self) -> dict[str, Any]:
        """Return the fields that map onto the `items` table."""
        return {
            "name": self.name,
            "brand": self.brand,
            "category": self.category,
            "subcategory": self.subcategory,
            "current_value": self.estimated_value_aud,
            "condition": self.condition,
        }

    def to_dict(self) -> dict[str, Any]:
        """Return the suggestion as a plain dictionary."""
        return {
            "name": self.name,
            "brand": self.brand,
            "category": self.category,
            "subcategory": self.subcategory,
            "estimated_value_aud": self.estimated_value_aud,
            "condition": self.condition,
            "region": list(self.region) if self.region else None,
        }


@dataclass(frozen=True, slots=True)
class RecognitionResult:
    """Everything one recognition call produced."""

    suggestions: tuple[ItemSuggestion, ...]
    model: str
    duration_ms: int
    raw_response: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Return the result as a plain dictionary."""
        return {
            "suggestions": [s.to_dict() for s in self.suggestions],
            "model": self.model,
            "duration_ms": self.duration_ms,
            "count": len(self.suggestions),
        }


# --------------------------------------------------------------------------
# Service
# --------------------------------------------------------------------------


class AIService:
    """A small asynchronous client for the Ollama HTTP API."""

    def __init__(self, config: OllamaConfig | None = None) -> None:
        self.config = config or OllamaConfig.from_settings()

    # -- public API --------------------------------------------------------

    async def status(self) -> AIStatus:
        """Return the state of Ollama. This call never raises."""
        config = self.config
        if not config.enabled:
            return AIStatus(
                enabled=False,
                available=False,
                base_url=config.base_url,
                model=config.model,
                text_model=config.text_model,
                error="HS_AI_ENABLED is false.",
            )
        try:
            async with self._client(timeout=STATUS_TIMEOUT) as client:
                version, tags, running = await asyncio.gather(
                    self._get_json(client, "/api/version"),
                    self._get_json(client, "/api/tags"),
                    self._get_json(client, "/api/ps"),
                    return_exceptions=True,
                )
        except Exception as exc:
            return self._unreachable(str(exc))

        if isinstance(tags, BaseException):
            return self._unreachable(str(tags))

        models = tuple(
            str(m.get("name", ""))
            for m in (tags or {}).get("models", [])
            if m.get("name")
        )
        loaded: tuple[str, ...] = ()
        gpu: bool | None = None
        if isinstance(running, dict):
            entries = running.get("models", [])
            loaded = tuple(str(m.get("name", "")) for m in entries if m.get("name"))
            if entries:
                gpu = any(int(m.get("size_vram", 0) or 0) > 0 for m in entries)

        return AIStatus(
            enabled=True,
            available=True,
            base_url=config.base_url,
            model=config.model,
            text_model=config.text_model,
            model_present=self._model_present(config.model, models),
            text_model_present=self._model_present(config.text_model, models),
            models=models,
            version=(version or {}).get("version")
            if isinstance(version, dict)
            else None,
            gpu=gpu,
            loaded_models=loaded,
        )

    async def recognize(self, image: bytes) -> RecognitionResult:
        """Identify the items in one photograph."""
        return await self._recognize_with(ITEM_RECOGNITION_PROMPT, image)

    async def bulk_scan(self, image: bytes) -> RecognitionResult:
        """Identify every item in a photograph of a shelf, drawer, or area."""
        return await self._recognize_with(
            ITEM_RECOGNITION_PROMPT + BULK_SCAN_SUFFIX, image
        )

    async def parse_receipt(
        self, image: bytes | None = None, *, raw_text: str | None = None
    ) -> dict[str, Any]:
        """Return the structured content of one receipt.

        The server has no GPU. Text inference is several times faster than
        vision inference on a CPU, so a receipt that Tesseract could read goes
        to the text model, and only an unreadable one goes to the vision
        model with the image.
        """
        prompt = RECEIPT_PARSE_PROMPT
        has_text = bool(raw_text and len(raw_text.strip()) >= MIN_OCR_TEXT_CHARS)

        if has_text:
            prompt = (
                f"{prompt}\n\nThe OCR text of the receipt follows. Read the "
                f"values out of it.\n\n{(raw_text or '').strip()[:6000]}"
            )
            response = await self.generate(prompt, model=self.config.text_model)
        elif image:
            response = await self.generate(prompt, images=[image])
        else:
            raise UpstreamError("The receipt has neither text nor an image.")
        payload = extract_json_payload(response)
        if not isinstance(payload, dict):
            raise UpstreamError(
                "The model did not return a receipt object.",
                details={"response": response[:500]},
            )
        return payload

    async def generate(
        self,
        prompt: str,
        *,
        images: list[bytes] | None = None,
        json_format: bool = True,
        temperature: float = 0.1,
        model: str | None = None,
    ) -> str:
        """Send one prompt to Ollama and return the raw text answer."""
        config = self.config
        if not config.enabled:
            raise AIUnavailableError(
                "The AI features are off. Set HS_AI_ENABLED to true to use them."
            )
        wanted_model = model or config.model

        body: dict[str, Any] = {
            "model": wanted_model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": temperature},
        }
        if json_format:
            body["format"] = "json"
        if images:
            body["images"] = [
                base64.b64encode(image).decode("ascii") for image in images
            ]

        try:
            async with self._client() as client:
                response = await client.post("/api/generate", json=body)
                response.raise_for_status()
                data = response.json()
        except httpx.TimeoutException as exc:
            raise AIUnavailableError(
                f"Ollama did not answer in {config.timeout:.0f} seconds."
            ) from exc
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text[:300]
            if exc.response.status_code == 404:
                raise AIUnavailableError(
                    f"Ollama does not have the model '{wanted_model}'. "
                    f"Run: ollama pull {wanted_model}"
                ) from exc
            raise UpstreamError(
                f"Ollama answered with status {exc.response.status_code}.",
                details={"body": detail},
            ) from exc
        except httpx.HTTPError as exc:
            raise AIUnavailableError(
                f"Ollama at {config.base_url} is not reachable: {exc}"
            ) from exc

        return str(data.get("response", ""))

    # -- internals ---------------------------------------------------------

    async def _recognize_with(self, prompt: str, image: bytes) -> RecognitionResult:
        """Run one vision prompt and parse the item list out of the answer."""
        if not image:
            raise UpstreamError("The image is empty.")
        loop = asyncio.get_running_loop()
        started = loop.time()
        response = await self.generate(prompt, images=[image])
        duration_ms = int((loop.time() - started) * 1000)

        payload = extract_json_payload(response)
        suggestions = tuple(
            suggestion
            for suggestion in (
                parse_suggestion(entry) for entry in _as_item_list(payload)
            )
            if suggestion is not None
        )
        if not suggestions:
            logger.info(
                "The vision model returned no usable item. Response: %s",
                response[:300],
            )
        return RecognitionResult(
            suggestions=suggestions,
            model=self.config.model,
            duration_ms=duration_ms,
            raw_response=response,
        )

    def _client(self, *, timeout: float | None = None) -> httpx.AsyncClient:
        """Return an HTTP client that points at Ollama."""
        return httpx.AsyncClient(
            base_url=self.config.base_url.rstrip("/"),
            timeout=timeout or self.config.timeout,
        )

    @staticmethod
    async def _get_json(client: httpx.AsyncClient, path: str) -> dict[str, Any]:
        """GET one JSON document."""
        response = await client.get(path)
        response.raise_for_status()
        result = response.json()
        return result if isinstance(result, dict) else {}

    def _unreachable(self, error: str) -> AIStatus:
        """Build the status that says Ollama did not answer."""
        return AIStatus(
            enabled=True,
            available=False,
            base_url=self.config.base_url,
            model=self.config.model,
            text_model=self.config.text_model,
            error=error,
        )

    @staticmethod
    def _model_present(model: str, models: tuple[str, ...]) -> bool:
        """Return True if the configured model is one of the installed models."""
        wanted = model.split(":")[0]
        return any(name.split(":")[0] == wanted for name in models)


# --------------------------------------------------------------------------
# Parsing helpers
# --------------------------------------------------------------------------

_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)


def extract_json_payload(text: str) -> Any:
    """Find the JSON value inside a model answer.

    Models often wrap JSON in a code fence or add a sentence before it. This
    helper accepts all of those shapes and returns None if nothing parses.
    """
    if not text:
        return None
    candidates: list[str] = []

    fenced = _FENCE.search(text)
    if fenced:
        candidates.append(fenced.group(1))
    candidates.append(text)

    for candidate in candidates:
        stripped = candidate.strip()
        if not stripped:
            continue
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            pass
        block = _first_json_block(stripped)
        if block is not None:
            try:
                return json.loads(block)
            except json.JSONDecodeError:
                continue
    return None


def _first_json_block(text: str) -> str | None:
    """Return the first balanced JSON array or object in `text`."""
    starts = [index for index in (text.find("["), text.find("{")) if index != -1]
    if not starts:
        return None
    start = min(starts)
    opening = text[start]
    closing = "]" if opening == "[" else "}"
    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == opening:
            depth += 1
        elif char == closing:
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return None


def _as_item_list(payload: Any) -> list[dict[str, Any]]:
    """Normalise every shape that the model returns into a list of objects."""
    if payload is None:
        return []
    if isinstance(payload, list):
        return [entry for entry in payload if isinstance(entry, dict)]
    if isinstance(payload, dict):
        for key in ("items", "objects", "results", "suggestions", "products"):
            value = payload.get(key)
            if isinstance(value, list):
                return [entry for entry in value if isinstance(entry, dict)]
        if any(key in payload for key in ("name", "item", "title")):
            return [payload]
    return []


def parse_suggestion(entry: dict[str, Any]) -> ItemSuggestion | None:
    """Turn one raw object from the model into an `ItemSuggestion`."""
    name = _first_string(entry, ("name", "item", "title", "object"))
    if not name:
        return None
    return ItemSuggestion(
        name=name[:255],
        brand=_first_string(entry, ("brand", "manufacturer", "make")),
        category=_first_string(entry, ("category", "type")),
        subcategory=_first_string(entry, ("subcategory", "sub_category")),
        estimated_value_aud=coerce_number(
            entry.get("estimated_value_aud")
            if entry.get("estimated_value_aud") is not None
            else entry.get("estimated_value", entry.get("value"))
        ),
        condition=normalise_condition(entry.get("condition")),
        region=parse_region(entry),
        raw=entry,
    )


def parse_region(entry: dict[str, Any]) -> tuple[int, int, int, int] | None:
    """Read a bounding box of four numbers, as a bulk scan returns.

    A model that answers with words instead of numbers gives no box, and the
    client then shows the item without a highlight.
    """
    for key in ("region", "bbox", "box", "bounding_box"):
        value = entry.get(key)
        if not isinstance(value, list | tuple) or len(value) != 4:
            continue
        numbers = [coerce_number(part) for part in value]
        if any(number is None for number in numbers):
            continue
        box = tuple(int(number) for number in numbers)  # type: ignore[arg-type]
        return box  # type: ignore[return-value]
    return None


def _first_string(entry: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    """Return the first key of `keys` that holds a non-empty string."""
    for key in keys:
        value = entry.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def coerce_number(value: Any) -> float | None:
    """Read a number out of a number, or out of a string such as 'A$1,299.00'."""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        cleaned = re.sub(r"[^0-9.\-]", "", value.replace(",", ""))
        if cleaned in ("", "-", ".", "-."):
            return None
        try:
            return float(cleaned)
        except ValueError:
            return None
    return None


def normalise_condition(value: Any) -> str | None:
    """Return one of new, good, fair, or poor, else None."""
    if not isinstance(value, str):
        return None
    candidate = value.strip().lower()
    if candidate in VALID_CONDITIONS:
        return candidate
    for known in ("new", "good", "fair", "poor"):
        if known in candidate:
            return known
    return None


def get_ai_service() -> AIService:
    """Build a service that reads its configuration from the environment."""
    return AIService()


__all__ = [
    "BULK_SCAN_SUFFIX",
    "ITEM_RECOGNITION_PROMPT",
    "RECEIPT_PARSE_PROMPT",
    "AIService",
    "AIStatus",
    "ItemSuggestion",
    "OllamaConfig",
    "RecognitionResult",
    "coerce_number",
    "extract_json_payload",
    "get_ai_service",
    "normalise_condition",
    "parse_region",
    "parse_suggestion",
]
