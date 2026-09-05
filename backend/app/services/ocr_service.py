"""Receipt reading: Tesseract for the text, Ollama for the structure.

The pipeline has three steps and every step can fail without stopping the
next one:

1. Tesseract extracts the raw text. If Tesseract is absent, the text is empty.
2. The vision model turns the image and the raw text into structured JSON.
3. If the model is unavailable, a text-only parser fills in what it can.
"""

from __future__ import annotations

import calendar
import logging
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from io import BytesIO
from typing import Any, Final

import anyio.to_thread

from app.services.ai_service import AIService, coerce_number
from app.services.errors import AIUnavailableError, ServiceError, UpstreamError
from app.utils.settings import setting

logger = logging.getLogger(__name__)

DEFAULT_CURRENCY: Final[str] = "AUD"
MAX_RAW_TEXT_CHARS: Final[int] = 20000

_MONTHS: Final[dict[str, int]] = {
    name.lower(): number for number, name in enumerate(calendar.month_abbr) if name
}


@dataclass(frozen=True, slots=True)
class ReceiptLine:
    """One line of a receipt."""

    name: str
    quantity: float | None = None
    unit_price: float | None = None
    total: float | None = None

    def to_dict(self) -> dict[str, Any]:
        """Return the line as a plain dictionary."""
        return {
            "name": self.name,
            "quantity": self.quantity,
            "unit_price": self.unit_price,
            "total": self.total,
        }


@dataclass(frozen=True, slots=True)
class ParsedReceipt:
    """The structured content of one receipt."""

    store_name: str | None = None
    purchase_date: date | None = None
    lines: tuple[ReceiptLine, ...] = ()
    subtotal: float | None = None
    tax: float | None = None
    grand_total: float | None = None
    currency: str | None = None
    raw_text: str = ""
    source: str = "none"
    parsed_json: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return the receipt as a plain dictionary."""
        return {
            "store_name": self.store_name,
            "date": self.purchase_date.isoformat() if self.purchase_date else None,
            "items": [line.to_dict() for line in self.lines],
            "subtotal": self.subtotal,
            "tax": self.tax,
            "grand_total": self.grand_total,
            "currency": self.currency,
            "source": self.source,
        }

    def to_receipt_columns(self) -> dict[str, Any]:
        """Return the fields that map onto the `receipts` table."""
        return {
            "vendor": self.store_name,
            "purchase_date": self.purchase_date,
            "total_amount": self.grand_total,
            "currency": self.currency or DEFAULT_CURRENCY,
            "ocr_raw_text": self.raw_text,
            "ocr_parsed_json": self.parsed_json or self.to_dict(),
        }


class OCRService:
    """Read one receipt image and return structured data."""

    def __init__(
        self,
        *,
        ai: AIService | None = None,
        tesseract_cmd: str | None = None,
    ) -> None:
        self.ai = ai or AIService()
        self.tesseract_cmd = tesseract_cmd or str(setting("tesseract_cmd", "") or "")

    # -- public API --------------------------------------------------------

    async def extract_text(self, image: bytes) -> str:
        """Return the raw text of an image. An empty string means no OCR."""
        return await anyio.to_thread.run_sync(lambda: self._tesseract(image))

    async def tesseract_available(self) -> bool:
        """Return True if the Tesseract binary answers."""
        return await anyio.to_thread.run_sync(self._tesseract_version) is not None

    async def parse(self, image: bytes, *, use_ai: bool = True) -> ParsedReceipt:
        """Run the whole receipt pipeline and return the best result."""
        raw_text = await self.extract_text(image)

        if use_ai:
            try:
                payload = await self.ai.parse_receipt(image, raw_text=raw_text)
                return build_parsed_receipt(payload, raw_text=raw_text, source="ollama")
            except (AIUnavailableError, UpstreamError) as exc:
                logger.info("The vision model did not parse the receipt: %s", exc)
            except ServiceError as exc:  # pragma: no cover - defensive
                logger.warning("The receipt parse failed: %s", exc)

        parsed = parse_receipt_text(raw_text)
        if not raw_text.strip():
            logger.info("No OCR text and no model answer. The receipt is empty.")
        return parsed

    # -- internals ---------------------------------------------------------

    def _tesseract(self, image: bytes) -> str:
        """Run Tesseract on the image bytes. Return "" if it is not installed."""
        try:
            import pytesseract
            from PIL import Image
        except ImportError:  # pragma: no cover - the container installs both
            logger.warning("pytesseract or Pillow is missing.")
            return ""

        self._apply_cmd(pytesseract)
        try:
            with Image.open(BytesIO(image)) as source:
                text = pytesseract.image_to_string(source)
        except pytesseract.TesseractNotFoundError:
            logger.warning(
                "Tesseract is not installed. The receipt keeps its raw image only."
            )
            return ""
        except Exception as exc:
            logger.warning("Tesseract failed: %s", exc)
            return ""
        return text[:MAX_RAW_TEXT_CHARS]

    def _tesseract_version(self) -> str | None:
        """Return the Tesseract version, or None if the binary is absent."""
        try:
            import pytesseract
        except ImportError:  # pragma: no cover
            return None
        self._apply_cmd(pytesseract)
        try:
            return str(pytesseract.get_tesseract_version())
        except Exception:
            return None

    def _apply_cmd(self, pytesseract: Any) -> None:
        """Point pytesseract at the configured binary."""
        if self.tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = self.tesseract_cmd


# --------------------------------------------------------------------------
# Model answer -> ParsedReceipt
# --------------------------------------------------------------------------


def build_parsed_receipt(
    payload: dict[str, Any], *, raw_text: str = "", source: str = "ollama"
) -> ParsedReceipt:
    """Turn the JSON answer of the vision model into a `ParsedReceipt`."""
    lines: list[ReceiptLine] = []
    for entry in payload.get("items") or []:
        if not isinstance(entry, dict):
            continue
        name = entry.get("name")
        if not isinstance(name, str) or not name.strip():
            continue
        lines.append(
            ReceiptLine(
                name=name.strip()[:255],
                quantity=coerce_number(entry.get("quantity")),
                unit_price=coerce_number(entry.get("unit_price")),
                total=coerce_number(entry.get("total")),
            )
        )

    currency = payload.get("currency")
    return ParsedReceipt(
        store_name=_clean_text(payload.get("store_name")),
        purchase_date=parse_date(payload.get("date")),
        lines=tuple(lines),
        subtotal=coerce_number(payload.get("subtotal")),
        tax=coerce_number(payload.get("tax")),
        grand_total=coerce_number(payload.get("grand_total")),
        currency=(
            currency.strip().upper()[:3]
            if isinstance(currency, str) and currency.strip()
            else None
        ),
        raw_text=raw_text,
        source=source,
        parsed_json=payload,
    )


def _clean_text(value: Any) -> str | None:
    """Return a trimmed string, or None if the value is empty or not a string."""
    if isinstance(value, str) and value.strip():
        return value.strip()[:255]
    return None


# --------------------------------------------------------------------------
# Text-only fallback parser
# --------------------------------------------------------------------------

_AMOUNT = re.compile(r"(-?\$?\s?\d[\d,]*\.\d{2})")
_DATE_PATTERNS: Final[tuple[re.Pattern[str], ...]] = (
    re.compile(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b"),
    re.compile(r"\b(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})\b"),
    re.compile(r"\b(\d{1,2})[/.-](\d{1,2})[/.-](\d{2})\b"),
    re.compile(r"\b(\d{1,2})\s+([A-Za-z]{3,9})\.?\s+(\d{4})\b"),
)


def parse_receipt_text(raw_text: str) -> ParsedReceipt:
    """Read what is readable out of the OCR text alone.

    This runs when Ollama is not available. It is deliberately conservative:
    a field that is not clear stays None, and the user corrects it.
    """
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    if not lines:
        return ParsedReceipt(raw_text=raw_text, source="none")

    return ParsedReceipt(
        store_name=_guess_store(lines),
        purchase_date=_find_date(raw_text),
        lines=tuple(_guess_lines(lines)),
        subtotal=_find_labelled_amount(lines, ("subtotal", "sub total")),
        tax=_find_labelled_amount(lines, ("gst", "tax", "vat")),
        grand_total=_find_total(lines),
        currency=_guess_currency(raw_text),
        raw_text=raw_text,
        source="text",
    )


def _guess_store(lines: list[str]) -> str | None:
    """The store name is almost always in the first readable lines."""
    for line in lines[:5]:
        letters = sum(char.isalpha() for char in line)
        if letters >= 3 and len(line) <= 40 and not _AMOUNT.search(line):
            return line.strip(" *-=_")
    return None


def _find_date(text: str) -> date | None:
    """Find the first date. Day comes before month, as in Australia."""
    for pattern in _DATE_PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        parsed = parse_date(match.group(0))
        if parsed:
            return parsed
    return None


def _find_labelled_amount(lines: list[str], labels: tuple[str, ...]) -> float | None:
    """Return the amount on the last line that carries one of the labels."""
    found: float | None = None
    for line in lines:
        lowered = line.lower()
        if any(label in lowered for label in labels):
            amount = _last_amount(line)
            if amount is not None:
                found = amount
    return found


def _find_total(lines: list[str]) -> float | None:
    """Return the grand total, and never confuse it with the subtotal."""
    for label in ("grand total", "total due", "amount due", "total"):
        for line in reversed(lines):
            lowered = line.lower()
            if "subtotal" in lowered or "sub total" in lowered:
                continue
            if label in lowered:
                amount = _last_amount(line)
                if amount is not None:
                    return amount
    return None


def _guess_lines(lines: list[str]) -> list[ReceiptLine]:
    """Return the lines that look like an article and a price."""
    skip = (
        "subtotal",
        "sub total",
        "total",
        "gst",
        "tax",
        "vat",
        "change",
        "cash",
        "eftpos",
        "visa",
        "mastercard",
        "card",
        "balance",
        "tender",
        "abn",
        "invoice",
        "receipt",
        "thank",
        "www",
        "phone",
        "tel",
    )
    result: list[ReceiptLine] = []
    for line in lines:
        lowered = line.lower()
        if any(word in lowered for word in skip):
            continue
        amount = _last_amount(line)
        if amount is None:
            continue
        name = _AMOUNT.sub("", line).strip(" .-*x$")
        if len(name) < 2:
            continue
        result.append(ReceiptLine(name=name[:255], total=amount))
    return result[:100]


def _last_amount(line: str) -> float | None:
    """Return the last decimal amount on one line."""
    matches = _AMOUNT.findall(line)
    if not matches:
        return None
    return coerce_number(matches[-1])


def _guess_currency(text: str) -> str | None:
    """Return the currency code. Australian receipts are the common case."""
    upper = text.upper()
    for code in ("AUD", "NZD", "USD", "GBP", "EUR", "CAD"):
        if code in upper:
            return code
    if "GST" in upper or "$" in text:
        return DEFAULT_CURRENCY
    return None


def parse_date(value: Any) -> date | None:
    """Read a date out of a date, a datetime, or common written forms."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()

    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        pass

    for pattern in _DATE_PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        parts = match.groups()
        try:
            if pattern.pattern.startswith(r"\b(\d{4})"):
                return date(int(parts[0]), int(parts[1]), int(parts[2]))
            if parts[1].isalpha():
                month = _MONTHS.get(parts[1][:3].lower())
                if month is None:
                    continue
                return date(int(parts[2]), month, int(parts[0]))
            year = int(parts[2])
            if year < 100:
                year += 2000
            return date(year, int(parts[1]), int(parts[0]))
        except ValueError:
            continue
    return None


def get_ocr_service() -> OCRService:
    """Build a service that reads its configuration from the environment."""
    return OCRService()


__all__ = [
    "DEFAULT_CURRENCY",
    "OCRService",
    "ParsedReceipt",
    "ReceiptLine",
    "build_parsed_receipt",
    "get_ocr_service",
    "parse_date",
    "parse_receipt_text",
]
