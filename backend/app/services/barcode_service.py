"""Barcode lookup against free product databases.

The service asks Open Food Facts first, because it is open data and has no
request limit. If that database does not know the code, it asks the UPCitemdb
trial endpoint. A code that neither database knows returns None, and the user
types the details by hand.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Final

import httpx

from app.services.errors import UpstreamError

logger = logging.getLogger(__name__)

OPEN_FOOD_FACTS_URL: Final[str] = "https://world.openfoodfacts.org/api/v2/product"
UPCITEMDB_URL: Final[str] = "https://api.upcitemdb.com/prod/trial/lookup"
USER_AGENT: Final[str] = "HomeStock/1.0 (self-hosted home inventory)"
DEFAULT_TIMEOUT: Final[float] = 10.0

SOURCE_OPEN_FOOD_FACTS: Final[str] = "openfoodfacts"
SOURCE_UPCITEMDB: Final[str] = "upcitemdb"

_VALID_LENGTHS: Final[frozenset[int]] = frozenset({8, 12, 13, 14})


class InvalidBarcodeError(ValueError):
    """The scanned text is not a product barcode."""


@dataclass(frozen=True, slots=True)
class ProductInfo:
    """One product, as the lookup databases describe it."""

    barcode: str
    name: str
    brand: str | None = None
    category: str | None = None
    subcategory: str | None = None
    description: str | None = None
    image_url: str | None = None
    size: str | None = None
    source: str = ""
    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return the product as a plain dictionary."""
        return {
            "barcode": self.barcode,
            "name": self.name,
            "brand": self.brand,
            "category": self.category,
            "subcategory": self.subcategory,
            "description": self.description,
            "image_url": self.image_url,
            "size": self.size,
            "source": self.source,
        }

    def to_item_payload(self) -> dict[str, Any]:
        """Return the fields that map onto the `items` table."""
        return {
            "name": self.name,
            "brand": self.brand,
            "category": self.category,
            "subcategory": self.subcategory,
            "description": self.description,
            "barcode": self.barcode,
        }


class BarcodeService:
    """Look one barcode up in the free product databases."""

    def __init__(
        self,
        *,
        timeout: float = DEFAULT_TIMEOUT,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.timeout = timeout
        self._client = client

    async def lookup(self, barcode: str) -> ProductInfo | None:
        """Return the product, or None if no database knows the code."""
        code = normalise_barcode(barcode)
        client = self._client
        if client is not None:
            return await self._lookup_with(client, code)
        async with httpx.AsyncClient(
            timeout=self.timeout, headers={"User-Agent": USER_AGENT}
        ) as owned:
            return await self._lookup_with(owned, code)

    async def _lookup_with(
        self, client: httpx.AsyncClient, code: str
    ) -> ProductInfo | None:
        """Ask each database in turn."""
        for source in (self._open_food_facts, self._upcitemdb):
            try:
                product = await source(client, code)
            except httpx.HTTPError as exc:
                logger.info("The barcode lookup at %s failed: %s", source.__name__, exc)
                continue
            if product is not None:
                return product
        return None

    async def _open_food_facts(
        self, client: httpx.AsyncClient, code: str
    ) -> ProductInfo | None:
        """Ask Open Food Facts."""
        response = await client.get(
            f"{OPEN_FOOD_FACTS_URL}/{code}.json",
            params={
                "fields": "product_name,product_name_en,brands,categories,"
                "generic_name,image_front_url,image_url,quantity,code"
            },
        )
        if response.status_code == 404:
            return None
        response.raise_for_status()
        payload = response.json()
        if not _off_found(payload):
            return None

        product = payload.get("product") or {}
        name = _text(product.get("product_name")) or _text(
            product.get("product_name_en")
        )
        if not name:
            return None
        categories = _split_list(product.get("categories")) or []
        return ProductInfo(
            barcode=code,
            name=name,
            brand=_first(_split_list(product.get("brands"))),
            category=categories[0] if categories else None,
            subcategory=categories[-1] if len(categories) > 1 else None,
            description=_text(product.get("generic_name")),
            image_url=_text(product.get("image_front_url"))
            or _text(product.get("image_url")),
            size=_text(product.get("quantity")),
            source=SOURCE_OPEN_FOOD_FACTS,
            raw=product,
        )

    async def _upcitemdb(
        self, client: httpx.AsyncClient, code: str
    ) -> ProductInfo | None:
        """Ask the UPCitemdb trial endpoint."""
        response = await client.get(UPCITEMDB_URL, params={"upc": code})
        if response.status_code in (404, 429):
            if response.status_code == 429:
                logger.info("UPCitemdb refused the request: the day limit is reached.")
            return None
        response.raise_for_status()
        payload = response.json()
        items = payload.get("items") or []
        if not items or not isinstance(items[0], dict):
            return None

        product = items[0]
        name = _text(product.get("title"))
        if not name:
            return None
        images = product.get("images") or []
        return ProductInfo(
            barcode=code,
            name=name,
            brand=_text(product.get("brand")),
            category=_text(product.get("category")),
            description=_text(product.get("description")),
            image_url=_text(images[0]) if images else None,
            size=_text(product.get("size")),
            source=SOURCE_UPCITEMDB,
            raw=product,
        )


def normalise_barcode(barcode: str) -> str:
    """Return the digits of a barcode, or raise `InvalidBarcodeError`."""
    if not barcode:
        raise InvalidBarcodeError("The barcode is empty.")
    digits = re.sub(r"[\s-]", "", str(barcode).strip())
    if not digits.isdigit():
        raise InvalidBarcodeError("A barcode holds digits only.")
    if len(digits) not in _VALID_LENGTHS:
        raise InvalidBarcodeError(
            f"A barcode has 8, 12, 13, or 14 digits. This code has {len(digits)}."
        )
    return digits


def _off_found(payload: dict[str, Any]) -> bool:
    """Return True if the Open Food Facts answer holds a product."""
    status = payload.get("status")
    if isinstance(status, int):
        return status == 1
    if isinstance(status, str):
        return status.lower() in ("1", "success", "found")
    return bool(payload.get("product"))


def _text(value: Any) -> str | None:
    """Return a trimmed string, or None."""
    if isinstance(value, str) and value.strip():
        return value.strip()[:500]
    return None


def _split_list(value: Any) -> list[str] | None:
    """Split a comma separated field into a list of names, or return None."""
    text = _text(value)
    if text is None:
        return None
    parts = [part.strip() for part in text.split(",") if part.strip()]
    return parts or None


def _first(values: list[str] | None) -> str | None:
    """Return the first entry of a list, or None."""
    return values[0] if values else None


def get_barcode_service() -> BarcodeService:
    """Build the default barcode service."""
    return BarcodeService()


__all__ = [
    "BarcodeService",
    "InvalidBarcodeError",
    "ProductInfo",
    "UpstreamError",
    "get_barcode_service",
    "normalise_barcode",
]
