"""Tag routes."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.models.tag import Tag
from app.schemas.common import Envelope, Message, ok
from app.schemas.item import ItemDetail
from app.schemas.tag import TagCreate, TagRead, TagUpdate
from app.utils.auth import CurrentUser, SessionDep
from app.utils.errors import conflict, not_found
from app.utils.queries import get_item_or_404, to_item_detail

router = APIRouter(prefix="/api/tags", tags=["Tags"])


async def _get_tag_or_404(session: SessionDep, tag_id: uuid.UUID) -> Tag:
    """Return one tag, or raise 404."""
    tag = await session.get(Tag, tag_id)
    if tag is None:
        raise not_found("The tag")
    return tag


@router.get("", response_model=Envelope[list[TagRead]], summary="List every tag.")
async def list_tags(
    user: CurrentUser, session: SessionDep
) -> Envelope[list[TagRead]]:
    rows = (await session.execute(select(Tag).order_by(Tag.name))).scalars().all()
    return ok([TagRead.model_validate(row) for row in rows])


@router.post(
    "",
    response_model=Envelope[TagRead],
    status_code=status.HTTP_201_CREATED,
    summary="Create a tag.",
)
async def create_tag(
    body: TagCreate, user: CurrentUser, session: SessionDep
) -> Envelope[TagRead]:
    name = body.name.strip()
    existing = await session.scalar(
        select(Tag).where(func.lower(Tag.name) == name.lower())
    )
    if existing is not None:
        raise conflict(f"The tag '{existing.name}' already exists.")

    tag = Tag(name=name, color=body.color)
    session.add(tag)
    try:
        await session.commit()
    except IntegrityError as exc:
        # Two clients created the same tag at the same moment.
        await session.rollback()
        raise conflict(f"The tag '{name}' already exists.") from exc
    await session.refresh(tag)
    return ok(TagRead.model_validate(tag))


@router.put(
    "/{tag_id}", response_model=Envelope[TagRead], summary="Rename or recolour a tag."
)
async def update_tag(
    tag_id: uuid.UUID, body: TagUpdate, user: CurrentUser, session: SessionDep
) -> Envelope[TagRead]:
    tag = await _get_tag_or_404(session, tag_id)
    changes = body.model_dump(exclude_unset=True)

    if "name" in changes and changes["name"]:
        name = changes["name"].strip()
        clash = await session.scalar(
            select(Tag).where(func.lower(Tag.name) == name.lower(), Tag.id != tag_id)
        )
        if clash is not None:
            raise conflict(f"The tag '{clash.name}' already exists.")
        changes["name"] = name

    for field, value in changes.items():
        setattr(tag, field, value)
    await session.commit()
    await session.refresh(tag)
    return ok(TagRead.model_validate(tag))


@router.delete(
    "/{tag_id}",
    response_model=Envelope[Message],
    summary="Delete a tag and remove it from every item.",
)
async def delete_tag(
    tag_id: uuid.UUID, user: CurrentUser, session: SessionDep
) -> Envelope[Message]:
    tag = await _get_tag_or_404(session, tag_id)
    # The item_tags rows go with it, through ON DELETE CASCADE.
    await session.delete(tag)
    await session.commit()
    return ok(Message(message="The tag is deleted."))


# --- Assigning a tag to an item ---
#
# These two routes are not in the original route list. PUT /api/items/{id}
# can set the whole tag list, but the mobile application needs to add or
# remove one tag without sending the rest of the item.


@router.post(
    "/{tag_id}/items/{item_id}",
    response_model=Envelope[ItemDetail],
    summary="Put a tag on an item.",
)
async def assign_tag(
    tag_id: uuid.UUID, item_id: uuid.UUID, user: CurrentUser, session: SessionDep
) -> Envelope[ItemDetail]:
    tag = await _get_tag_or_404(session, tag_id)
    item = await get_item_or_404(session, item_id, user, with_relations=True)
    if all(existing.id != tag.id for existing in item.tags):
        item.tags.append(tag)
        item.version += 1
        await session.commit()
        await session.refresh(item, ["photos", "tags"])
    return ok(await to_item_detail(session, item))


@router.delete(
    "/{tag_id}/items/{item_id}",
    response_model=Envelope[ItemDetail],
    summary="Take a tag off an item.",
)
async def remove_tag(
    tag_id: uuid.UUID, item_id: uuid.UUID, user: CurrentUser, session: SessionDep
) -> Envelope[ItemDetail]:
    item = await get_item_or_404(session, item_id, user, with_relations=True)
    remaining = [tag for tag in item.tags if tag.id != tag_id]
    if len(remaining) != len(item.tags):
        item.tags = remaining
        item.version += 1
        await session.commit()
        await session.refresh(item, ["photos", "tags"])
    return ok(await to_item_detail(session, item))
