"""Photograph routes for a component and for a cable.

The two owners need the same six actions, so one set of helpers serves both.
An item keeps its own routes, because an item photograph also carries the OCR
text.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, File, UploadFile, status
from sqlalchemy import select

from app.models.cable import Cable
from app.models.component import Component
from app.models.photo import Photo
from app.models.user import User
from app.schemas.common import Envelope, Message, ok
from app.schemas.photo import PhotoRow, PhotoUpdate
from app.utils.auth import CurrentUser, SessionDep
from app.utils.errors import ApiError, not_found
from app.utils.queries import read_upload
from app.utils.thumbnails import (
    UnsupportedImageError,
    UploadKind,
    delete_image_set,
    store_image,
)

router = APIRouter(prefix="/api", tags=["Photographs"])

#: The upload directory and the model for each owner.
OWNERS: dict[str, tuple[UploadKind, type[Component] | type[Cable]]] = {
    "component": ("components", Component),
    "cable": ("cables", Cable),
}


# --------------------------------------------------------------------------
# Shared work
# --------------------------------------------------------------------------


async def _owner_or_404(
    session: SessionDep, owner_type: str, owner_id: uuid.UUID, user: User
) -> None:
    """Raise 404 unless this user owns a live row of that kind."""
    _, model = OWNERS[owner_type]
    found = await session.scalar(
        select(model.id).where(
            model.id == owner_id,
            model.user_id == user.id,
            model.deleted_at.is_(None),
        )
    )
    if found is None:
        raise not_found(f"The {owner_type}")


async def _photos_of(
    session: SessionDep, owner_type: str, owner_id: uuid.UUID
) -> list[Photo]:
    """Return the live photographs of one owner. The thumbnail comes first."""
    rows = await session.execute(
        select(Photo)
        .where(
            Photo.owner_type == owner_type,
            Photo.owner_id == owner_id,
            Photo.deleted_at.is_(None),
        )
        .order_by(Photo.is_primary.desc(), Photo.sort_order, Photo.created_at)
    )
    return list(rows.scalars().all())


async def _get_photo_or_404(
    session: SessionDep, photo_id: uuid.UUID, user: User
) -> Photo:
    """Return one live photograph of this user, or raise 404."""
    photo = (
        await session.execute(
            select(Photo).where(
                Photo.id == photo_id,
                Photo.user_id == user.id,
                Photo.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if photo is None:
        raise not_found("The photograph")
    return photo


async def _upload(
    session: SessionDep,
    user: User,
    owner_type: str,
    owner_id: uuid.UUID,
    files: list[UploadFile],
) -> list[PhotoRow]:
    """Store every uploaded image and write one row for each."""
    await _owner_or_404(session, owner_type, owner_id, user)
    kind, _ = OWNERS[owner_type]

    existing = await _photos_of(session, owner_type, owner_id)
    has_primary = any(photo.is_primary for photo in existing)
    next_order = len(existing)

    created: list[Photo] = []
    for upload in files:
        data = await read_upload(upload)
        try:
            stored = await store_image(data, kind=kind, entity_id=owner_id)
        except UnsupportedImageError as exc:
            raise ApiError(
                status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "bad_image", str(exc)
            ) from exc

        thumbnails = stored.relative_thumbnails
        photo = Photo(
            user_id=user.id,
            owner_type=owner_type,
            owner_id=owner_id,
            file_path=stored.relative_original,
            thumbnail_path=(thumbnails[min(thumbnails)] if thumbnails else None),
            # The first picture of an owner becomes the thumbnail, so a list
            # never shows an empty square while a photograph exists.
            is_primary=not has_primary,
            sort_order=next_order,
        )
        has_primary = True
        next_order += 1
        session.add(photo)
        created.append(photo)

    await session.commit()
    for photo in created:
        await session.refresh(photo)
    return [PhotoRow.model_validate(photo) for photo in created]


async def primary_thumbnails(
    session: SessionDep, owner_type: str, owner_ids: list[uuid.UUID]
) -> dict[uuid.UUID, str]:
    """Return the thumbnail of each owner in the list, by owner id.

    The list views call this once for the whole page, instead of once for
    each row.
    """
    if not owner_ids:
        return {}
    rows = await session.execute(
        select(Photo.owner_id, Photo.thumbnail_path, Photo.file_path)
        .where(
            Photo.owner_type == owner_type,
            Photo.owner_id.in_(owner_ids),
            Photo.is_primary.is_(True),
            Photo.deleted_at.is_(None),
        )
        .order_by(Photo.created_at)
    )
    return {row[0]: (row[1] or row[2]) for row in rows}


async def count_photos(
    session: SessionDep, owner_type: str, owner_ids: list[uuid.UUID]
) -> dict[uuid.UUID, int]:
    """Return how many photographs each owner in the list has."""
    if not owner_ids:
        return {}
    rows = await session.execute(
        select(Photo.owner_id).where(
            Photo.owner_type == owner_type,
            Photo.owner_id.in_(owner_ids),
            Photo.deleted_at.is_(None),
        )
    )
    counts: dict[uuid.UUID, int] = {}
    for row in rows:
        counts[row[0]] = counts.get(row[0], 0) + 1
    return counts


# --------------------------------------------------------------------------
# The routes of each owner
# --------------------------------------------------------------------------


@router.get(
    "/components/{component_id}/photos",
    response_model=Envelope[list[PhotoRow]],
    summary="List the photographs of a component.",
)
async def list_component_photos(
    component_id: uuid.UUID, user: CurrentUser, session: SessionDep
) -> Envelope[list[PhotoRow]]:
    await _owner_or_404(session, "component", component_id, user)
    rows = await _photos_of(session, "component", component_id)
    return ok([PhotoRow.model_validate(row) for row in rows])


@router.post(
    "/components/{component_id}/photos",
    response_model=Envelope[list[PhotoRow]],
    status_code=status.HTTP_201_CREATED,
    summary="Upload one or more photographs of a component.",
)
async def upload_component_photos(
    component_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
    files: Annotated[list[UploadFile], File(description="One or more images.")],
) -> Envelope[list[PhotoRow]]:
    return ok(await _upload(session, user, "component", component_id, files))


@router.get(
    "/cables/{cable_id}/photos",
    response_model=Envelope[list[PhotoRow]],
    summary="List the photographs of a cable.",
)
async def list_cable_photos(
    cable_id: uuid.UUID, user: CurrentUser, session: SessionDep
) -> Envelope[list[PhotoRow]]:
    await _owner_or_404(session, "cable", cable_id, user)
    rows = await _photos_of(session, "cable", cable_id)
    return ok([PhotoRow.model_validate(row) for row in rows])


@router.post(
    "/cables/{cable_id}/photos",
    response_model=Envelope[list[PhotoRow]],
    status_code=status.HTTP_201_CREATED,
    summary="Upload one or more photographs of a cable.",
)
async def upload_cable_photos(
    cable_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
    files: Annotated[list[UploadFile], File(description="One or more images.")],
) -> Envelope[list[PhotoRow]]:
    return ok(await _upload(session, user, "cable", cable_id, files))


# --------------------------------------------------------------------------
# One photograph
# --------------------------------------------------------------------------


@router.put(
    "/photos/{photo_id}/primary",
    response_model=Envelope[list[PhotoRow]],
    summary="Make this photograph the thumbnail of its owner.",
    description="The other photographs of that owner lose the flag.",
)
async def set_primary_photo(
    photo_id: uuid.UUID, user: CurrentUser, session: SessionDep
) -> Envelope[list[PhotoRow]]:
    photo = await _get_photo_or_404(session, photo_id, user)
    siblings = await _photos_of(session, photo.owner_type, photo.owner_id)

    for row in siblings:
        wanted = row.id == photo.id
        if row.is_primary != wanted:
            row.is_primary = wanted
            row.version += 1

    await session.commit()
    rows = await _photos_of(session, photo.owner_type, photo.owner_id)
    return ok([PhotoRow.model_validate(row) for row in rows])


@router.put(
    "/photos/{photo_id}",
    response_model=Envelope[PhotoRow],
    summary="Change the caption or the order of a photograph.",
)
async def update_photo(
    photo_id: uuid.UUID, body: PhotoUpdate, user: CurrentUser, session: SessionDep
) -> Envelope[PhotoRow]:
    photo = await _get_photo_or_404(session, photo_id, user)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(photo, field, value)
    photo.version += 1
    await session.commit()
    await session.refresh(photo)
    return ok(PhotoRow.model_validate(photo))


@router.delete(
    "/photos/{photo_id}",
    response_model=Envelope[Message],
    summary="Delete one photograph and its thumbnails.",
)
async def delete_photo(
    photo_id: uuid.UUID, user: CurrentUser, session: SessionDep
) -> Envelope[Message]:
    photo = await _get_photo_or_404(session, photo_id, user)
    was_primary = photo.is_primary

    delete_image_set(photo.file_path)
    photo.deleted_at = datetime.now(UTC)
    photo.is_primary = False
    photo.version += 1
    await session.flush()

    if was_primary:
        # The owner keeps a thumbnail: the next picture takes the flag.
        remaining = await _photos_of(session, photo.owner_type, photo.owner_id)
        if remaining:
            remaining[0].is_primary = True
            remaining[0].version += 1

    await session.commit()
    return ok(Message(message="The photograph is deleted."))
