"""Write the activity log.

Every route that changes an item calls `record`. The call adds a row to the
session; the route commits it with the change itself, so the log can never
tell a story that did not happen.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity import Activity
from app.models.user import User

#: The fields that a person cares about, and the words for each one.
FIELD_WORDS: dict[str, str] = {
    "name": "the name",
    "description": "the description",
    "category": "the category",
    "subcategory": "the subcategory",
    "brand": "the brand",
    "model": "the model",
    "serial_number": "the serial number",
    "barcode": "the barcode",
    "purchase_price": "the price",
    "current_value": "the value",
    "purchase_date": "the purchase date",
    "purchase_location": "the shop",
    "warranty_expires": "the warranty date",
    "condition": "the condition",
    "quantity": "the count",
    "notes": "the notes",
    "owner": "the owner",
    "location_id": "the place",
    "tag_ids": "the tags",
}


def record(
    session: AsyncSession,
    *,
    user: User,
    entity_id: uuid.UUID,
    action: str,
    summary: str,
    detail: str | None = None,
    entity_type: str = "item",
) -> Activity:
    """Add one line to the log. The caller commits."""
    entry = Activity(
        user_id=user.id,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        summary=summary[:300],
        detail=detail,
        actor=user.name,
    )
    session.add(entry)
    return entry


def describe(value: Any) -> str:
    """Return one value as a person writes it."""
    if value is None or value == "":
        return "nothing"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, Decimal | float | int):
        return str(value)
    text = str(value)
    return text if len(text) <= 60 else f"{text[:57]}..."


def change_summary(changes: dict[str, Any], before: dict[str, Any]) -> tuple[str, str]:
    """Return the sentence and the detail for one edit.

    One field gives a sentence that names the old value and the new one. More
    fields give a count, and the detail lists them.
    """
    named = [field for field in changes if field in FIELD_WORDS]
    if not named:
        return ("The item changed.", "")

    lines = [
        f"{FIELD_WORDS[field].capitalize()}: "
        f"{describe(before.get(field))} to {describe(changes[field])}"
        for field in named
    ]
    if len(named) == 1:
        field = named[0]
        return (
            f"{FIELD_WORDS[field].capitalize()} changed from "
            f"{describe(before.get(field))} to {describe(changes[field])}.",
            "",
        )
    return (f"{len(named)} fields changed.", "\n".join(lines))
