"""Tests for the photographs of a component and of a cable."""

from __future__ import annotations

import io
from typing import Any

import pytest
from httpx import AsyncClient
from PIL import Image

from app.utils.thumbnails import to_absolute
from tests.conftest import register, sign_in

pytestmark = pytest.mark.asyncio(loop_scope="session")


def png_bytes(colour: str = "teal") -> bytes:
    """Return one PNG image for an upload test."""
    buffer = io.BytesIO()
    Image.new("RGB", (900, 700), colour).save(buffer, format="PNG")
    return buffer.getvalue()


def files(count: int = 1) -> list[tuple[str, tuple[str, bytes, str]]]:
    """Return an upload payload of `count` images."""
    return [
        ("files", (f"photo-{index}.png", png_bytes(), "image/png"))
        for index in range(count)
    ]


async def make_component(
    client: AsyncClient, headers: dict[str, str], name: str = "DeWalt battery"
) -> dict[str, Any]:
    response = await client.post(
        "/api/components", json={"name": name}, headers=headers
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


async def make_cable(
    client: AsyncClient, headers: dict[str, str], name: str = "USB-C lead"
) -> dict[str, Any]:
    response = await client.post("/api/cables", json={"name": name}, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()["data"]


async def test_a_component_takes_photographs(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    component = await make_component(client, headers)
    response = await client.post(
        f"/api/components/{component['id']}/photos", files=files(2), headers=headers
    )
    assert response.status_code == 201, response.text
    photos = response.json()["data"]
    assert len(photos) == 2
    assert photos[0]["is_primary"] is True
    assert photos[1]["is_primary"] is False
    assert photos[0]["owner_type"] == "component"

    assert to_absolute(photos[0]["file_path"]).exists()
    assert to_absolute(photos[0]["thumbnail_path"]).exists()


async def test_the_component_list_carries_the_thumbnail(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    component = await make_component(client, headers)
    upload = await client.post(
        f"/api/components/{component['id']}/photos", files=files(), headers=headers
    )
    thumbnail = upload.json()["data"][0]["thumbnail_path"]

    response = await client.get("/api/components", headers=headers)
    row = response.json()["data"][0]
    assert row["thumbnail_path"] == thumbnail
    assert row["photo_count"] == 1


async def test_a_cable_takes_photographs(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    cable = await make_cable(client, headers)
    response = await client.post(
        f"/api/cables/{cable['id']}/photos", files=files(), headers=headers
    )
    assert response.status_code == 201, response.text
    assert response.json()["data"][0]["owner_type"] == "cable"

    listing = await client.get("/api/cables", headers=headers)
    row = listing.json()["data"][0]
    assert row["photo_count"] == 1
    assert row["thumbnail_path"] is not None


async def test_the_thumbnail_moves_to_the_photograph_you_choose(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    component = await make_component(client, headers)
    upload = await client.post(
        f"/api/components/{component['id']}/photos", files=files(3), headers=headers
    )
    photos = upload.json()["data"]

    response = await client.put(
        f"/api/photos/{photos[2]['id']}/primary", headers=headers
    )
    assert response.status_code == 200
    rows = response.json()["data"]
    assert rows[0]["id"] == photos[2]["id"]
    assert rows[0]["is_primary"] is True
    assert [row["is_primary"] for row in rows].count(True) == 1


async def test_a_deleted_thumbnail_passes_the_flag_on(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    component = await make_component(client, headers)
    upload = await client.post(
        f"/api/components/{component['id']}/photos", files=files(2), headers=headers
    )
    photos = upload.json()["data"]
    first = to_absolute(photos[0]["file_path"])

    response = await client.delete(f"/api/photos/{photos[0]['id']}", headers=headers)
    assert response.status_code == 200
    assert not first.exists()

    listing = await client.get(
        f"/api/components/{component['id']}/photos", headers=headers
    )
    rows = listing.json()["data"]
    assert len(rows) == 1
    assert rows[0]["id"] == photos[1]["id"]
    assert rows[0]["is_primary"] is True


async def test_a_caption_is_saved(client: AsyncClient, headers: dict[str, str]) -> None:
    cable = await make_cable(client, headers)
    upload = await client.post(
        f"/api/cables/{cable['id']}/photos", files=files(), headers=headers
    )
    photo = upload.json()["data"][0]

    response = await client.put(
        f"/api/photos/{photo['id']}", json={"caption": "The label"}, headers=headers
    )
    assert response.status_code == 200
    assert response.json()["data"]["caption"] == "The label"


async def test_a_photograph_of_another_account_stays_hidden(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    component = await make_component(client, headers)
    upload = await client.post(
        f"/api/components/{component['id']}/photos", files=files(), headers=headers
    )
    photo = upload.json()["data"][0]

    other = await register(client)
    other_headers = await sign_in(client, other["email"])
    response = await client.delete(f"/api/photos/{photo['id']}", headers=other_headers)
    assert response.status_code == 404


async def test_a_component_of_another_account_takes_no_photograph(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    component = await make_component(client, headers)
    other = await register(client)
    other_headers = await sign_in(client, other["email"])

    response = await client.post(
        f"/api/components/{component['id']}/photos",
        files=files(),
        headers=other_headers,
    )
    assert response.status_code == 404


async def test_an_item_photograph_becomes_the_thumbnail(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    item = (
        await client.post("/api/items", json={"name": "Drill"}, headers=headers)
    ).json()["data"]
    upload = await client.post(
        f"/api/items/{item['id']}/photos", files=files(2), headers=headers
    )
    photos = upload.json()["data"]

    response = await client.put(
        f"/api/items/{item['id']}/photos/{photos[1]['id']}/primary", headers=headers
    )
    assert response.status_code == 200
    rows = response.json()["data"]
    chosen = next(row for row in rows if row["id"] == photos[1]["id"])
    assert chosen["is_primary"] is True
    assert [row["is_primary"] for row in rows].count(True) == 1


async def test_the_sync_carries_the_photographs(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    cable = await make_cable(client, headers)
    upload = await client.post(
        f"/api/cables/{cable['id']}/photos", files=files(), headers=headers
    )
    photo = upload.json()["data"][0]

    response = await client.get("/api/sync/changes", headers=headers)
    assert [row["id"] for row in response.json()["data"]["photos"]] == [photo["id"]]
