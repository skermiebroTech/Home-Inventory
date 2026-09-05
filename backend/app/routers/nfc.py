"""NFC routes."""

from __future__ import annotations

from fastapi import APIRouter, status
from sqlalchemy import func, select

from app.models.nfc import NfcTag
from app.schemas.common import Envelope, Message, ok
from app.schemas.nfc import NfcLookup, NfcRead, NfcRegister
from app.utils.auth import CurrentUser, SessionDep
from app.utils.errors import conflict, not_found
from app.utils.queries import get_item_or_404, get_location_or_404

router = APIRouter(prefix="/api/nfc", tags=["NFC"])


def _normalise_uid(nfc_uid: str) -> str:
    """Return the tag UID without separators, in upper case.

    Readers report the same tag as "04:A2:1B" or "04a21b". One stored form
    keeps the lookup reliable.
    """
    return nfc_uid.replace(":", "").replace("-", "").replace(" ", "").upper()


async def _find(session: SessionDep, nfc_uid: str) -> NfcTag | None:
    """Find a registered tag by UID."""
    return await session.scalar(
        select(NfcTag).where(func.upper(NfcTag.nfc_uid) == _normalise_uid(nfc_uid))
    )


@router.post(
    "/register",
    response_model=Envelope[NfcRead],
    status_code=status.HTTP_201_CREATED,
    summary="Bind an NFC tag to one item or to one location.",
)
async def register_tag(
    body: NfcRegister, user: CurrentUser, session: SessionDep
) -> Envelope[NfcRead]:
    uid = _normalise_uid(body.nfc_uid)
    if not uid:
        raise conflict("The tag UID is empty.")

    existing = await _find(session, uid)
    if existing is not None:
        raise conflict(
            "That tag is already registered. Delete it first to bind it again."
        )

    # The check also proves that the target belongs to the signed in user.
    if body.item_id is not None:
        await get_item_or_404(session, body.item_id, user)
    else:
        await get_location_or_404(session, body.location_id, user)

    tag = NfcTag(
        item_id=body.item_id,
        location_id=body.location_id,
        nfc_uid=uid,
        label=body.label,
    )
    session.add(tag)
    await session.commit()
    await session.refresh(tag)
    return ok(NfcRead.model_validate(tag))


@router.get(
    "/{nfc_uid}",
    response_model=Envelope[NfcLookup],
    summary="Return what a scanned NFC tag points at.",
)
async def lookup_tag(
    nfc_uid: str, user: CurrentUser, session: SessionDep
) -> Envelope[NfcLookup]:
    tag = await _find(session, nfc_uid)
    if tag is None:
        raise not_found("That NFC tag")

    if tag.item_id is not None:
        item = await get_item_or_404(session, tag.item_id, user)
        return ok(
            NfcLookup(
                nfc_uid=tag.nfc_uid,
                target_type="item",
                target_id=item.id,
                target_name=item.name,
            )
        )

    location = await get_location_or_404(session, tag.location_id, user)
    return ok(
        NfcLookup(
            nfc_uid=tag.nfc_uid,
            target_type="location",
            target_id=location.id,
            target_name=location.name,
        )
    )


@router.delete(
    "/{nfc_uid}",
    response_model=Envelope[Message],
    summary="Unbind an NFC tag.",
)
async def delete_tag(
    nfc_uid: str, user: CurrentUser, session: SessionDep
) -> Envelope[Message]:
    tag = await _find(session, nfc_uid)
    if tag is None:
        raise not_found("That NFC tag")

    # Prove ownership before the delete.
    if tag.item_id is not None:
        await get_item_or_404(session, tag.item_id, user)
    else:
        await get_location_or_404(session, tag.location_id, user)

    await session.delete(tag)
    await session.commit()
    return ok(Message(message="The NFC tag is unbound."))
