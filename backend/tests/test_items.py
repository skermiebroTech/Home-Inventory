"""Tests for the item routes: create, read, update, delete, and photographs."""

from __future__ import annotations

import asyncio
import io
from typing import Any

import pytest
from httpx import AsyncClient
from PIL import Image

from tests.conftest import register, sign_in

pytestmark = pytest.mark.asyncio(loop_scope="session")


def png_bytes(size: tuple[int, int] = (1200, 900), colour: str = "teal") -> bytes:
    """Return one PNG image for an upload test."""
    buffer = io.BytesIO()
    Image.new("RGB", size, colour).save(buffer, format="PNG")
    return buffer.getvalue()


def jpeg_with_gps() -> bytes:
    """Return one JPEG that carries GPS coordinates in its EXIF block."""
    image = Image.new("RGB", (800, 600), "peru")
    exif = Image.Exif()
    exif[0x010F] = "TestCamera"
    exif[0x8825] = {1: "S", 2: (27.0, 28.0, 0.0), 3: "E", 4: (153.0, 1.0, 0.0)}
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", exif=exif)
    return buffer.getvalue()


async def make_item(
    client: AsyncClient, headers: dict[str, str], **fields: Any
) -> dict[str, Any]:
    """Create one item and return it."""
    body = {"name": "Test item", **fields}
    response = await client.post("/api/items", json=body, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()["data"]


async def make_location(
    client: AsyncClient, headers: dict[str, str], name: str, **fields: Any
) -> dict[str, Any]:
    """Create one location and return it."""
    response = await client.post(
        "/api/locations", json={"name": name, **fields}, headers=headers
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


# --------------------------------------------------------------------------
# Create and read
# --------------------------------------------------------------------------


async def test_create_item(client: AsyncClient, headers: dict[str, str]) -> None:
    response = await client.post(
        "/api/items",
        json={
            "name": "  DeWalt DCD771 cordless drill  ",
            "category": "Tools",
            "brand": "DeWalt",
            "purchase_price": "199.00",
            "quantity": 2,
            "condition": "good",
        },
        headers=headers,
    )
    assert response.status_code == 201
    item = response.json()["data"]
    assert item["name"] == "DeWalt DCD771 cordless drill"
    assert item["quantity"] == 2
    assert item["version"] == 1
    assert item["tags"] == []
    assert item["photos"] == []
    assert item["is_lent"] is False


async def test_create_item_needs_a_token(client: AsyncClient) -> None:
    response = await client.post("/api/items", json={"name": "No token"})
    assert response.status_code == 401


async def test_create_item_in_a_location(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    garage = await make_location(client, headers, "Garage", type="room")
    shelf = await make_location(
        client, headers, "Top shelf", type="zone", parent_id=garage["id"]
    )
    item = await make_item(client, headers, name="Paint tin", location_id=shelf["id"])
    assert item["location_id"] == shelf["id"]
    assert item["location_path"] == ["Garage", "Top shelf"]


async def test_create_item_refuses_an_unknown_location(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    response = await client.post(
        "/api/items",
        json={
            "name": "Nowhere",
            "location_id": "00000000-0000-4000-8000-000000000000",
        },
        headers=headers,
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


async def test_get_item(client: AsyncClient, headers: dict[str, str]) -> None:
    created = await make_item(client, headers, name="Ladder")
    response = await client.get(f"/api/items/{created['id']}", headers=headers)
    assert response.status_code == 200
    assert response.json()["data"]["name"] == "Ladder"


async def test_get_unknown_item(client: AsyncClient, headers: dict[str, str]) -> None:
    response = await client.get(
        "/api/items/00000000-0000-4000-8000-000000000000", headers=headers
    )
    assert response.status_code == 404


# --------------------------------------------------------------------------
# Listing, filtering, and pages
# --------------------------------------------------------------------------


async def test_list_pages(client: AsyncClient, headers: dict[str, str]) -> None:
    for index in range(5):
        await make_item(client, headers, name=f"Item {index}")

    response = await client.get("/api/items?per_page=2&page=1", headers=headers)
    page = response.json()["data"]
    assert page["total"] == 5
    assert page["pages"] == 3
    assert len(page["items"]) == 2

    last = await client.get("/api/items?per_page=2&page=3", headers=headers)
    assert len(last.json()["data"]["items"]) == 1


async def test_list_filters_by_category_and_condition(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    await make_item(client, headers, name="Drill", category="Tools", condition="good")
    await make_item(client, headers, name="Sofa", category="Furniture")

    tools = await client.get("/api/items?category=Tools", headers=headers)
    assert [i["name"] for i in tools.json()["data"]["items"]] == ["Drill"]

    good = await client.get("/api/items?condition=good", headers=headers)
    assert [i["name"] for i in good.json()["data"]["items"]] == ["Drill"]


async def test_list_filters_by_location_and_its_children(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    garage = await make_location(client, headers, "Garage")
    bench = await make_location(
        client, headers, "Work bench", type="container", parent_id=garage["id"]
    )
    kitchen = await make_location(client, headers, "Kitchen")
    await make_item(client, headers, name="Spanner", location_id=bench["id"])
    await make_item(client, headers, name="Kettle", location_id=kitchen["id"])

    deep = await client.get(f"/api/items?location_id={garage['id']}", headers=headers)
    assert [i["name"] for i in deep.json()["data"]["items"]] == ["Spanner"]

    shallow = await client.get(
        f"/api/items?location_id={garage['id']}&include_sublocations=false",
        headers=headers,
    )
    assert shallow.json()["data"]["items"] == []


async def test_list_filters_by_tag(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    tag = (
        await client.post("/api/tags", json={"name": "Power tools"}, headers=headers)
    ).json()["data"]
    tagged = await make_item(client, headers, name="Circular saw", tag_ids=[tag["id"]])
    await make_item(client, headers, name="Cushion")

    response = await client.get(f"/api/items?tag_id={tag['id']}", headers=headers)
    items = response.json()["data"]["items"]
    assert [i["id"] for i in items] == [tagged["id"]]
    assert items[0]["tags"][0]["name"] == "Power tools"


async def test_list_refuses_an_unknown_sort_field(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    response = await client.get("/api/items?sort=-secret", headers=headers)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_sort"


async def test_list_sorts_by_name(client: AsyncClient, headers: dict[str, str]) -> None:
    for name in ("Chisel", "Anvil", "Bandsaw"):
        await make_item(client, headers, name=name)
    response = await client.get("/api/items?sort=name", headers=headers)
    names = [i["name"] for i in response.json()["data"]["items"]]
    assert names == ["Anvil", "Bandsaw", "Chisel"]


# --------------------------------------------------------------------------
# Full text search
# --------------------------------------------------------------------------


async def test_search_finds_a_whole_word(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    await make_item(
        client,
        headers,
        name="DeWalt DCD771 cordless drill",
        description="Two batteries and a charger.",
        brand="DeWalt",
    )
    await make_item(client, headers, name="Garden hose")

    response = await client.get("/api/items/search?q=drill", headers=headers)
    assert response.status_code == 200
    names = [i["name"] for i in response.json()["data"]["items"]]
    assert names == ["DeWalt DCD771 cordless drill"]


async def test_search_reads_the_description_and_the_notes(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    await make_item(client, headers, name="Blue box", notes="Holds the spare fuses.")
    response = await client.get("/api/items/search?q=fuses", headers=headers)
    assert [i["name"] for i in response.json()["data"]["items"]] == ["Blue box"]


async def test_search_finds_a_partial_word(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    await make_item(client, headers, name="DeWalt DCD771 cordless drill")
    response = await client.get("/api/items/search?q=dewa", headers=headers)
    assert len(response.json()["data"]["items"]) == 1


async def test_search_returns_nothing_for_an_unrelated_word(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    await make_item(client, headers, name="Lawn mower")
    response = await client.get("/api/items/search?q=submarine", headers=headers)
    assert response.json()["data"]["items"] == []
    assert response.json()["data"]["total"] == 0


# --------------------------------------------------------------------------
# Update and delete
# --------------------------------------------------------------------------


async def test_update_changes_fields_and_raises_the_version(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    item = await make_item(client, headers, name="Old name", quantity=1)
    response = await client.put(
        f"/api/items/{item['id']}",
        json={"name": "New name", "quantity": 4, "notes": "Moved to the shed."},
        headers=headers,
    )
    assert response.status_code == 200
    updated = response.json()["data"]
    assert updated["name"] == "New name"
    assert updated["quantity"] == 4
    assert updated["version"] == item["version"] + 1


async def test_update_replaces_the_tag_list(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    first = (
        await client.post("/api/tags", json={"name": "Loud"}, headers=headers)
    ).json()["data"]
    second = (
        await client.post("/api/tags", json={"name": "Heavy"}, headers=headers)
    ).json()["data"]
    item = await make_item(client, headers, tag_ids=[first["id"]])

    response = await client.put(
        f"/api/items/{item['id']}",
        json={"tag_ids": [second["id"]]},
        headers=headers,
    )
    assert [t["name"] for t in response.json()["data"]["tags"]] == ["Heavy"]


async def test_delete_hides_the_item_but_keeps_the_row(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    item = await make_item(client, headers, name="Broken kettle")

    response = await client.delete(f"/api/items/{item['id']}", headers=headers)
    assert response.status_code == 200

    assert (
        await client.get(f"/api/items/{item['id']}", headers=headers)
    ).status_code == 404
    listing = await client.get("/api/items", headers=headers)
    assert listing.json()["data"]["total"] == 0

    # The row stays, so that the mobile application learns about the delete.
    from sqlalchemy import select

    from app.database import SessionLocal
    from app.models.item import Item

    async with SessionLocal() as session:
        row = (
            await session.execute(select(Item).where(Item.id == item["id"]))
        ).scalar_one()
        assert row.deleted_at is not None


async def test_bulk_create(client: AsyncClient, headers: dict[str, str]) -> None:
    response = await client.post(
        "/api/items/bulk",
        json={
            "items": [
                {"name": "Hammer", "category": "Tools"},
                {"name": "Saw", "category": "Tools"},
            ]
        },
        headers=headers,
    )
    assert response.status_code == 201
    created = response.json()["data"]
    assert [i["name"] for i in created] == ["Hammer", "Saw"]

    listing = await client.get("/api/items", headers=headers)
    assert listing.json()["data"]["total"] == 2


# --------------------------------------------------------------------------
# One account cannot reach another account
# --------------------------------------------------------------------------


async def test_an_item_is_private_to_its_owner(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    item = await make_item(client, headers, name="Private thing")

    await register(client, email="intruder@example.com")
    other = await sign_in(client, "intruder@example.com")

    assert (
        await client.get(f"/api/items/{item['id']}", headers=other)
    ).status_code == 404
    assert (
        await client.put(
            f"/api/items/{item['id']}", json={"name": "Taken"}, headers=other
        )
    ).status_code == 404
    assert (
        await client.delete(f"/api/items/{item['id']}", headers=other)
    ).status_code == 404
    assert (await client.get("/api/items", headers=other)).json()["data"]["total"] == 0


# --------------------------------------------------------------------------
# Photographs
# --------------------------------------------------------------------------


async def test_photo_upload_makes_thumbnails(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    from app.utils.thumbnails import to_absolute

    item = await make_item(client, headers, name="Bicycle")
    response = await client.post(
        f"/api/items/{item['id']}/photos",
        files=[
            ("files", ("front.png", png_bytes(), "image/png")),
            ("files", ("side.png", png_bytes((400, 300), "olive"), "image/png")),
        ],
        headers=headers,
    )
    assert response.status_code == 201
    photos = response.json()["data"]
    assert len(photos) == 2
    assert photos[0]["is_primary"] is True
    assert photos[1]["is_primary"] is False

    original = to_absolute(photos[0]["file_path"])
    thumbnail = to_absolute(photos[0]["thumbnail_path"])
    assert original.is_file()
    assert thumbnail.is_file()

    # The original is resized to the configured ceiling, and both thumbnail
    # widths are written beside it.
    with Image.open(original) as stored:
        assert max(stored.size) <= 2000
    with Image.open(thumbnail) as small:
        assert small.width == 200
    wide = original.with_name(f"{original.stem}_600{original.suffix}")
    assert wide.is_file()

    detail = await client.get(f"/api/items/{item['id']}", headers=headers)
    assert detail.json()["data"]["primary_photo"]["id"] == photos[0]["id"]


async def test_photo_upload_removes_the_gps_position(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    from app.utils.thumbnails import GPS_IFD_TAG, to_absolute

    source = jpeg_with_gps()
    with Image.open(io.BytesIO(source)) as before:
        assert GPS_IFD_TAG in before.getexif(), "the test image needs GPS data"

    item = await make_item(client, headers, name="Camera")
    response = await client.post(
        f"/api/items/{item['id']}/photos",
        files=[("files", ("holiday.jpg", source, "image/jpeg"))],
        headers=headers,
    )
    assert response.status_code == 201

    stored = to_absolute(response.json()["data"][0]["file_path"])
    with Image.open(stored) as after:
        assert GPS_IFD_TAG not in after.getexif()


async def test_photo_upload_refuses_a_file_that_is_not_an_image(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    item = await make_item(client, headers, name="Toolbox")
    response = await client.post(
        f"/api/items/{item['id']}/photos",
        files=[("files", ("notes.txt", b"plain text", "text/plain"))],
        headers=headers,
    )
    assert response.status_code == 415


async def test_delete_photo_removes_the_files_and_promotes_the_next(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    from app.utils.thumbnails import to_absolute

    item = await make_item(client, headers, name="Trailer")
    upload = await client.post(
        f"/api/items/{item['id']}/photos",
        files=[
            ("files", ("one.png", png_bytes((300, 200)), "image/png")),
            ("files", ("two.png", png_bytes((300, 200), "navy"), "image/png")),
        ],
        headers=headers,
    )
    photos = upload.json()["data"]
    original = to_absolute(photos[0]["file_path"])

    response = await client.delete(
        f"/api/items/{item['id']}/photos/{photos[0]['id']}", headers=headers
    )
    assert response.status_code == 200
    assert not original.exists()

    detail = await client.get(f"/api/items/{item['id']}", headers=headers)
    remaining = detail.json()["data"]["photos"]
    assert len(remaining) == 1
    assert remaining[0]["id"] == photos[1]["id"]
    assert remaining[0]["is_primary"] is True


async def test_photo_upload_reads_the_text_on_the_photograph(
    client: AsyncClient, headers: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The upload answers at once, and the OCR fills the row after it."""
    import app.routers.items as items_router

    class FakeOCR:
        async def extract_text(self, _image: bytes) -> str:
            return "DEWALT DCD771\nTYPE 1  18V\nS/N 4821994"

    monkeypatch.setattr(items_router, "OCRService", FakeOCR)

    item = await make_item(client, headers, name="Drill with a rating plate")
    response = await client.post(
        f"/api/items/{item['id']}/photos",
        files=[("files", ("plate.png", png_bytes((500, 400)), "image/png"))],
        headers=headers,
    )
    assert response.status_code == 201
    # The reply does not wait for the text.
    assert response.json()["data"][0]["ocr_text"] is None

    photo_id = response.json()["data"][0]["id"]
    for _ in range(40):
        detail = await client.get(f"/api/items/{item['id']}", headers=headers)
        photo = next(p for p in detail.json()["data"]["photos"] if p["id"] == photo_id)
        if photo["ocr_text"]:
            break
        await asyncio.sleep(0.05)

    assert "DCD771" in photo["ocr_text"]
    assert "4821994" in photo["ocr_text"]


async def test_a_photograph_with_no_text_stores_nothing(
    client: AsyncClient, headers: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    import app.routers.items as items_router

    class SilentOCR:
        async def extract_text(self, _image: bytes) -> str:
            return "   "

    monkeypatch.setattr(items_router, "OCRService", SilentOCR)

    item = await make_item(client, headers, name="Plain box")
    response = await client.post(
        f"/api/items/{item['id']}/photos",
        files=[("files", ("box.png", png_bytes((300, 300)), "image/png"))],
        headers=headers,
    )
    assert response.status_code == 201

    await asyncio.sleep(0.4)
    detail = await client.get(f"/api/items/{item['id']}", headers=headers)
    assert detail.json()["data"]["photos"][0]["ocr_text"] is None


async def test_many_photographs_upload_together(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    item = await make_item(client, headers, name="Machine from four sides")
    response = await client.post(
        f"/api/items/{item['id']}/photos",
        files=[
            ("files", (f"side-{index}.png", png_bytes((400, 300)), "image/png"))
            for index in range(4)
        ],
        headers=headers,
    )
    assert response.status_code == 201
    photos = response.json()["data"]
    assert len(photos) == 4
    # Only the first one is the primary photograph.
    assert [p["is_primary"] for p in photos] == [True, False, False, False]
