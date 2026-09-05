"""Item routes.

Route order matters. FastAPI matches routes in the order it registers them,
so every fixed path must come before ``/{item_id}``. Otherwise a request for
``/api/items/search`` matches ``/{item_id}`` and fails to parse a UUID.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, File, Query, UploadFile, status
from sqlalchemy import ColumnElement, Select, or_, select
from sqlalchemy import func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import SessionLocal
from app.models.item import Item, ItemPhoto
from app.models.tag import Tag
from app.models.user import User
from app.schemas.barcode import BarcodeProduct
from app.schemas.common import Envelope, Message, Page, ok
from app.schemas.item import (
    ItemBulkCreate,
    ItemCreate,
    ItemDetail,
    ItemPhotoRead,
    ItemRead,
    ItemUpdate,
)
from app.services.activity_service import change_summary, record
from app.services.barcode_service import InvalidBarcodeError, get_barcode_service
from app.services.job_service import get_job_store
from app.services.ocr_service import OCRService
from app.utils.auth import CurrentUser, SessionDep
from app.utils.errors import ApiError, not_found
from app.utils.queries import (
    build_page,
    descendant_location_ids,
    get_item_or_404,
    get_location_or_404,
    paginate,
    read_upload,
    reload_item,
    to_item_detail,
    to_item_read,
)
from app.utils.thumbnails import UnsupportedImageError, delete_image_set, store_image

router = APIRouter(prefix="/api/items", tags=["Items"])

#: The columns that ``sort`` accepts. Anything else is refused, because the
#: value reaches the ORDER BY clause.
SORTABLE = {
    "created_at": Item.created_at,
    "updated_at": Item.updated_at,
    "name": Item.name,
    "category": Item.category,
    "quantity": Item.quantity,
    "purchase_date": Item.purchase_date,
    "purchase_price": Item.purchase_price,
    "current_value": Item.current_value,
    "warranty_expires": Item.warranty_expires,
}

TEXT_SEARCH_CONFIG = "english"


def _base_query(user: User) -> Select[Any]:
    """Return the query that every item list starts from."""
    return (
        select(Item)
        .where(Item.user_id == user.id, Item.deleted_at.is_(None))
        .options(selectinload(Item.photos), selectinload(Item.tags))
    )


def _search_condition(q: str) -> ColumnElement[bool]:
    """Match the PostgreSQL full-text index, or a plain substring.

    The generated ``search_vector`` column covers name, description, brand,
    model, and notes. ``websearch_to_tsquery`` understands quoted phrases and
    the word OR. A tsquery matches whole words only, so a substring match on
    the name is kept as well. That is what makes a partial word such as
    "dewa" find the DeWalt drill.
    """
    tsquery = sa_func.websearch_to_tsquery(TEXT_SEARCH_CONFIG, q)
    like = f"%{q.strip()}%"
    return or_(
        Item.search_vector.op("@@")(tsquery),
        Item.name.ilike(like),
        Item.brand.ilike(like),
        Item.model.ilike(like),
        Item.serial_number.ilike(like),
    )


def _rank(q: str) -> ColumnElement[float]:
    """Return the full-text rank of a row, for ORDER BY."""
    return sa_func.ts_rank(
        Item.search_vector, sa_func.websearch_to_tsquery(TEXT_SEARCH_CONFIG, q)
    )


def _apply_sort(statement: Select[Any], sort: str) -> Select[Any]:
    """Order a list query. A leading minus reverses the direction."""
    descending = sort.startswith("-")
    field = sort[1:] if descending else sort
    column = SORTABLE.get(field)
    if column is None:
        raise ApiError(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "invalid_sort",
            f"'{field}' is not a sortable field.",
            {"sortable": sorted(SORTABLE)},
        )
    return statement.order_by(
        column.desc().nullslast() if descending else column.asc().nullsfirst(),
        Item.id,
    )


async def _resolve_tags(session: AsyncSession, tag_ids: list[uuid.UUID]) -> list[Tag]:
    """Return the tag rows for a list of ids, or raise 404."""
    if not tag_ids:
        return []
    wanted = list(dict.fromkeys(tag_ids))
    tags = (
        (await session.execute(select(Tag).where(Tag.id.in_(wanted)))).scalars().all()
    )
    if len(tags) != len(wanted):
        missing = set(wanted) - {tag.id for tag in tags}
        raise not_found(f"The tag {sorted(str(m) for m in missing)[0]}")
    return list(tags)


async def _new_item(session: AsyncSession, body: ItemCreate, user: User) -> Item:
    """Build one item row from a create body. The caller commits."""
    if body.location_id is not None:
        await get_location_or_404(session, body.location_id, user)
    fields = body.model_dump(exclude={"tag_ids"})
    fields["name"] = fields["name"].strip()
    item = Item(user_id=user.id, **fields)
    item.tags = await _resolve_tags(session, body.tag_ids)
    session.add(item)
    return item


# --- Fixed paths. These must stay above the /{item_id} routes. ---


@router.get(
    "",
    response_model=Envelope[Page[ItemRead]],
    summary="List items with filters, sorting, and pages.",
)
async def list_items(
    user: CurrentUser,
    session: SessionDep,
    q: Annotated[str | None, Query(description="Full text search terms.")] = None,
    location_id: uuid.UUID | None = None,
    include_sublocations: bool = True,
    category: str | None = None,
    tag_id: Annotated[list[uuid.UUID] | None, Query()] = None,
    is_lent: bool | None = None,
    condition: Annotated[str | None, Query(pattern="^(new|good|fair|poor)$")] = None,
    owner: Annotated[str | None, Query(description="The person who owns it.")] = None,
    warranty_expiring_days: Annotated[int | None, Query(ge=0)] = None,
    sort: Annotated[
        str, Query(description="Prefix with - to reverse.")
    ] = "-created_at",
    page: Annotated[int, Query(ge=1)] = 1,
    per_page: Annotated[int, Query(ge=1, le=200)] = 50,
) -> Envelope[Page[ItemRead]]:
    statement = _base_query(user)

    if q and q.strip():
        statement = statement.where(_search_condition(q))
    if location_id is not None:
        if include_sublocations:
            wanted = await descendant_location_ids(session, location_id, user.id)
            statement = statement.where(Item.location_id.in_(wanted or [location_id]))
        else:
            statement = statement.where(Item.location_id == location_id)
    if category:
        statement = statement.where(Item.category == category)
    if tag_id:
        # Every named tag must be present, so that two filters narrow the list.
        for wanted_tag in dict.fromkeys(tag_id):
            statement = statement.where(Item.tags.any(Tag.id == wanted_tag))
    if is_lent is not None:
        statement = statement.where(Item.is_lent.is_(is_lent))
    if condition:
        statement = statement.where(Item.condition == condition)
    if owner:
        statement = statement.where(Item.owner == owner)
    if warranty_expiring_days is not None:
        today = date.today()
        statement = statement.where(
            Item.warranty_expires.is_not(None),
            Item.warranty_expires >= today,
            Item.warranty_expires <= today + timedelta(days=warranty_expiring_days),
        )

    if q and q.strip():
        statement = statement.order_by(_rank(q).desc(), Item.name.asc(), Item.id)
    else:
        statement = _apply_sort(statement, sort)

    rows, total, pages = await paginate(
        session, statement, page=page, per_page=per_page
    )
    return ok(
        build_page([to_item_read(row) for row in rows], total, page, per_page, pages)
    )


@router.get(
    "/owners",
    response_model=Envelope[list[str]],
    summary="List the people who own something.",
    description="The names that the items already carry. The field is free text.",
)
async def list_owners(user: CurrentUser, session: SessionDep) -> Envelope[list[str]]:
    rows = await session.execute(
        select(Item.owner)
        .where(
            Item.user_id == user.id,
            Item.deleted_at.is_(None),
            Item.owner.is_not(None),
            Item.owner != "",
        )
        .group_by(Item.owner)
        .order_by(sa_func.lower(Item.owner))
    )
    return ok([row[0] for row in rows])


@router.post(
    "",
    response_model=Envelope[ItemDetail],
    status_code=status.HTTP_201_CREATED,
    summary="Create one item.",
)
async def create_item(
    body: ItemCreate, user: CurrentUser, session: SessionDep
) -> Envelope[ItemDetail]:
    item = await _new_item(session, body, user)
    await session.flush()
    record(
        session,
        user=user,
        entity_id=item.id,
        action="created",
        summary=f"{item.name} was added.",
    )
    await session.commit()
    await reload_item(session, item)
    return ok(await to_item_detail(session, item))


@router.get(
    "/search",
    response_model=Envelope[Page[ItemRead]],
    summary="Full text search over name, description, brand, model, and notes.",
    description=(
        "PostgreSQL ranks the results with the generated tsvector column on "
        "the items table."
    ),
)
async def search_items(
    user: CurrentUser,
    session: SessionDep,
    q: Annotated[str, Query(min_length=1)],
    page: Annotated[int, Query(ge=1)] = 1,
    per_page: Annotated[int, Query(ge=1, le=200)] = 50,
) -> Envelope[Page[ItemRead]]:
    statement = (
        _base_query(user)
        .where(_search_condition(q))
        .order_by(_rank(q).desc(), Item.name.asc(), Item.id)
    )
    rows, total, pages = await paginate(
        session, statement, page=page, per_page=per_page
    )
    return ok(
        build_page([to_item_read(row) for row in rows], total, page, per_page, pages)
    )


@router.post(
    "/bulk",
    response_model=Envelope[list[ItemDetail]],
    status_code=status.HTTP_201_CREATED,
    summary="Create many items at once, after an AI bulk scan.",
)
async def bulk_create_items(
    body: ItemBulkCreate, user: CurrentUser, session: SessionDep
) -> Envelope[list[ItemDetail]]:
    created = [await _new_item(session, entry, user) for entry in body.items]
    await session.commit()
    details: list[ItemDetail] = []
    for item in created:
        await reload_item(session, item)
        details.append(await to_item_detail(session, item))
    return ok(details)


@router.get(
    "/barcode/{code}",
    response_model=Envelope[BarcodeProduct],
    tags=["Barcode"],
    summary="Look up a barcode in the public product databases.",
    description=(
        "This route is not in the original route list. The barcode service "
        "needs an entry point, and the mobile scanner calls it before it "
        "creates an item. It tries Open Food Facts, then UPCitemdb."
    ),
)
async def lookup_barcode(
    code: str, user: CurrentUser, session: SessionDep
) -> Envelope[BarcodeProduct]:
    product = await _lookup_barcode(code)
    return ok(
        BarcodeProduct(
            barcode=product.barcode,
            name=product.name,
            brand=product.brand,
            category=product.category,
            description=product.description,
            image_url=product.image_url,
            source=product.source,
        )
    )


@router.post(
    "/barcode/{code}",
    response_model=Envelope[ItemDetail],
    status_code=status.HTTP_201_CREATED,
    tags=["Barcode"],
    summary="Look a barcode up and create the item from the result.",
    description=(
        "This route is not in the original route list. It is the second half "
        "of the barcode flow: the scanner may create the item in one call "
        "instead of reading the product and posting it back."
    ),
)
async def create_item_from_barcode(
    code: str,
    user: CurrentUser,
    session: SessionDep,
    location_id: Annotated[uuid.UUID | None, Query()] = None,
    quantity: Annotated[int, Query(ge=1)] = 1,
) -> Envelope[ItemDetail]:
    product = await _lookup_barcode(code)
    payload = product.to_item_payload()
    item = await _new_item(
        session,
        ItemCreate(
            name=payload["name"][:300],
            brand=payload["brand"],
            category=payload["category"],
            subcategory=payload["subcategory"],
            description=payload["description"],
            barcode=payload["barcode"],
            location_id=location_id,
            quantity=quantity,
        ),
        user,
    )
    await session.commit()
    await reload_item(session, item)
    return ok(await to_item_detail(session, item))


async def _lookup_barcode(code: str) -> Any:
    """Ask the barcode databases, and turn a miss into a 404."""
    try:
        product = await get_barcode_service().lookup(code)
    except InvalidBarcodeError as exc:
        raise ApiError(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "invalid_barcode", str(exc)
        ) from exc
    if product is None:
        raise not_found(f"The barcode {code}")
    return product


# --- Paths with an item id. ---


@router.get(
    "/{item_id}", response_model=Envelope[ItemDetail], summary="Return one item."
)
async def get_item(
    item_id: uuid.UUID, user: CurrentUser, session: SessionDep
) -> Envelope[ItemDetail]:
    item = await get_item_or_404(session, item_id, user, with_relations=True)
    return ok(await to_item_detail(session, item))


@router.put(
    "/{item_id}", response_model=Envelope[ItemDetail], summary="Change an item."
)
async def update_item(
    item_id: uuid.UUID, body: ItemUpdate, user: CurrentUser, session: SessionDep
) -> Envelope[ItemDetail]:
    item = await get_item_or_404(session, item_id, user, with_relations=True)
    changes = body.model_dump(exclude_unset=True)

    if changes.get("location_id") is not None:
        await get_location_or_404(session, changes["location_id"], user)
    if "tag_ids" in changes:
        item.tags = await _resolve_tags(session, changes.pop("tag_ids") or [])

    # The old values are read before the write, so that the log can name both.
    before = {field: getattr(item, field, None) for field in changes}
    moved = "location_id" in changes and changes["location_id"] != item.location_id

    for field, value in changes.items():
        setattr(item, field, value.strip() if field == "name" and value else value)
    item.version += 1

    if changes:
        summary, detail = change_summary(changes, before)
        record(
            session,
            user=user,
            entity_id=item.id,
            action="moved" if moved and len(changes) == 1 else "changed",
            summary=summary,
            detail=detail or None,
        )

    await session.commit()
    await reload_item(session, item)
    return ok(await to_item_detail(session, item))


@router.delete(
    "/{item_id}",
    response_model=Envelope[Message],
    summary="Delete an item.",
    description=(
        "This is a soft delete. The row keeps a deleted_at value so that the "
        "mobile application learns about the deletion on its next sync."
    ),
)
async def delete_item(
    item_id: uuid.UUID, user: CurrentUser, session: SessionDep
) -> Envelope[Message]:
    item = await get_item_or_404(session, item_id, user)
    item.deleted_at = datetime.now(UTC)
    item.version += 1
    record(
        session,
        user=user,
        entity_id=item.id,
        action="deleted",
        summary=f"{item.name} was deleted.",
    )
    await session.commit()
    return ok(Message(message="The item is deleted."))


@router.post(
    "/{item_id}/photos",
    response_model=Envelope[list[ItemPhotoRead]],
    status_code=status.HTTP_201_CREATED,
    summary="Upload one or more photographs of an item.",
    description=(
        "The server resizes the original, generates the thumbnail sizes, and "
        "removes the EXIF GPS data."
    ),
)
async def upload_item_photos(
    item_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
    files: Annotated[list[UploadFile], File(description="One or more images.")],
) -> Envelope[list[ItemPhotoRead]]:
    item = await get_item_or_404(session, item_id, user, with_relations=True)
    has_primary = any(photo.is_primary for photo in item.photos)

    created: list[ItemPhoto] = []
    uploaded: list[bytes] = []
    for upload in files:
        data = await read_upload(upload)
        try:
            stored = await store_image(data, kind="items", entity_id=item.id)
        except UnsupportedImageError as exc:
            raise ApiError(
                status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "bad_image", str(exc)
            ) from exc

        thumbnail = stored.primary_thumbnail
        photo = ItemPhoto(
            item_id=item.id,
            file_path=stored.relative_original,
            thumbnail_path=(
                stored.relative_thumbnails[min(stored.thumbnails)]
                if thumbnail
                else None
            ),
            is_primary=not has_primary,
        )
        has_primary = True
        session.add(photo)
        created.append(photo)
        uploaded.append(data)

    # A new photograph changes what the mobile application shows for the item.
    item.version += 1
    if created:
        record(
            session,
            user=user,
            entity_id=item.id,
            action="photographed",
            summary=(
                "One photograph was added."
                if len(created) == 1
                else f"{len(created)} photographs were added."
            ),
        )
    await session.commit()
    for photo in created:
        await session.refresh(photo)

    # A label, a rating plate, or a box carries the model and the serial
    # number. Tesseract runs on the CPU, so it runs after the reply. The ids
    # are read here, not inside the task, because the task starts at the next
    # await and an ORM read during a refresh is a second use of one session.
    pending = [(photo.id, data) for photo, data in zip(created, uploaded, strict=True)]
    if pending:
        get_job_store().submit(
            kind="receipt_parse",
            user_id=user.id,
            work=lambda: _read_photo_text(pending),
        )

    return ok([ItemPhotoRead.model_validate(photo) for photo in created])


async def _read_photo_text(photos: list[tuple[uuid.UUID, bytes]]) -> int:
    """Read the text of each new photograph and write it onto the row.

    This runs after the upload reply, in its own session, because the request
    session closes with the request.
    """
    service = OCRService()
    found = 0
    async with SessionLocal() as session:
        for photo_id, data in photos:
            text = (await service.extract_text(data)).strip()
            if not text:
                continue
            photo = await session.get(ItemPhoto, photo_id)
            if photo is None:
                continue
            photo.ocr_text = text
            found += 1
        if found:
            await session.commit()
    return found


@router.put(
    "/{item_id}/photos/{photo_id}/primary",
    response_model=Envelope[list[ItemPhotoRead]],
    summary="Make this photograph the thumbnail of the item.",
    description="The other photographs of the item lose the flag.",
)
async def set_primary_item_photo(
    item_id: uuid.UUID, photo_id: uuid.UUID, user: CurrentUser, session: SessionDep
) -> Envelope[list[ItemPhotoRead]]:
    item = await get_item_or_404(session, item_id, user, with_relations=True)
    if not any(photo.id == photo_id for photo in item.photos):
        raise not_found("The photograph")

    for photo in item.photos:
        photo.is_primary = photo.id == photo_id
    item.version += 1
    record(
        session,
        user=user,
        entity_id=item.id,
        action="thumbnail_set",
        summary="The thumbnail changed.",
    )
    await session.commit()

    item = await get_item_or_404(session, item_id, user, with_relations=True)
    return ok([ItemPhotoRead.model_validate(photo) for photo in item.photos])


@router.delete(
    "/{item_id}/photos/{photo_id}",
    response_model=Envelope[Message],
    summary="Delete one photograph and its thumbnails.",
)
async def delete_item_photo(
    item_id: uuid.UUID, photo_id: uuid.UUID, user: CurrentUser, session: SessionDep
) -> Envelope[Message]:
    item = await get_item_or_404(session, item_id, user, with_relations=True)
    photo = next((p for p in item.photos if p.id == photo_id), None)
    if photo is None:
        raise not_found("The photograph")

    was_primary = photo.is_primary
    delete_image_set(photo.file_path)
    await session.delete(photo)
    await session.flush()

    if was_primary:
        # Promote the next photograph, so the item keeps a thumbnail.
        remaining = [p for p in item.photos if p.id != photo_id]
        if remaining:
            remaining[0].is_primary = True
    item.version += 1
    record(
        session,
        user=user,
        entity_id=item.id,
        action="photo_removed",
        summary="One photograph was deleted.",
    )

    await session.commit()
    return ok(Message(message="The photograph is deleted."))
