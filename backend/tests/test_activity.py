"""Tests for the owner of an item and for the activity log."""

from __future__ import annotations

import io
from typing import Any

import pytest
from httpx import AsyncClient
from PIL import Image

from tests.conftest import register, sign_in

pytestmark = pytest.mark.asyncio(loop_scope="session")


def png() -> tuple[str, tuple[str, bytes, str]]:
    """Return one upload payload entry."""
    buffer = io.BytesIO()
    Image.new("RGB", (400, 300), "olive").save(buffer, format="PNG")
    return ("files", ("photo.png", buffer.getvalue(), "image/png"))


async def make_item(
    client: AsyncClient, headers: dict[str, str], **fields: Any
) -> dict[str, Any]:
    body = {"name": "Honda mower", **fields}
    response = await client.post("/api/items", json=body, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()["data"]


async def log_of(
    client: AsyncClient, headers: dict[str, str], item_id: str
) -> list[dict[str, Any]]:
    response = await client.get(f"/api/items/{item_id}/activity", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()["data"]


# --------------------------------------------------------------------------
# The owner
# --------------------------------------------------------------------------


async def test_an_item_keeps_an_owner(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    item = await make_item(client, headers, owner="Joel")
    assert item["owner"] == "Joel"

    response = await client.get(f"/api/items/{item['id']}", headers=headers)
    assert response.json()["data"]["owner"] == "Joel"


async def test_the_list_filters_on_the_owner(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    await make_item(client, headers, name="Mower", owner="Joel")
    await make_item(client, headers, name="Bike", owner="Sam")

    response = await client.get("/api/items?owner=Sam", headers=headers)
    rows = response.json()["data"]["items"]
    assert [row["name"] for row in rows] == ["Bike"]


async def test_the_owner_list_holds_each_name_once(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    await make_item(client, headers, name="Mower", owner="Joel")
    await make_item(client, headers, name="Drill", owner="Joel")
    await make_item(client, headers, name="Bike", owner="Sam")
    await make_item(client, headers, name="Ladder")

    response = await client.get("/api/items/owners", headers=headers)
    assert response.json()["data"] == ["Joel", "Sam"]


# --------------------------------------------------------------------------
# The log
# --------------------------------------------------------------------------


async def test_a_new_item_starts_the_log(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    item = await make_item(client, headers)
    lines = await log_of(client, headers, item["id"])
    assert len(lines) == 1
    assert lines[0]["action"] == "created"
    assert lines[0]["summary"] == "Honda mower was added."
    assert lines[0]["actor"] == "Test Person"


async def test_one_changed_field_names_both_values(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    item = await make_item(client, headers)
    await client.put(
        f"/api/items/{item['id']}", json={"current_value": "899.00"}, headers=headers
    )

    lines = await log_of(client, headers, item["id"])
    assert lines[0]["action"] == "changed"
    assert lines[0]["summary"] == "The value changed from nothing to 899.00."


async def test_a_big_edit_lists_the_fields(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    item = await make_item(client, headers)
    await client.put(
        f"/api/items/{item['id']}",
        json={"brand": "Honda", "condition": "good", "owner": "Joel"},
        headers=headers,
    )

    lines = await log_of(client, headers, item["id"])
    assert lines[0]["summary"] == "3 fields changed."
    assert "The owner: nothing to Joel" in lines[0]["detail"]


async def test_the_log_follows_a_loan_and_a_return(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    item = await make_item(client, headers)
    await client.post(
        f"/api/items/{item['id']}/lend", json={"lent_to": "Dave"}, headers=headers
    )
    await client.post(f"/api/items/{item['id']}/return", headers=headers)

    actions = [line["action"] for line in await log_of(client, headers, item["id"])]
    assert actions[:2] == ["returned", "lent"]


async def test_the_log_follows_the_photographs(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    item = await make_item(client, headers)
    upload = await client.post(
        f"/api/items/{item['id']}/photos", files=[png(), png()], headers=headers
    )
    photos = upload.json()["data"]
    await client.put(
        f"/api/items/{item['id']}/photos/{photos[1]['id']}/primary", headers=headers
    )
    await client.delete(
        f"/api/items/{item['id']}/photos/{photos[0]['id']}", headers=headers
    )

    actions = [line["action"] for line in await log_of(client, headers, item["id"])]
    assert actions[:3] == ["photo_removed", "thumbnail_set", "photographed"]


async def test_the_log_follows_service_work(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    item = await make_item(client, headers)
    await client.post(
        f"/api/items/{item['id']}/maintenance",
        json={"description": "Changed the oil", "next_due_date": "2027-01-01"},
        headers=headers,
    )

    lines = await log_of(client, headers, item["id"])
    assert lines[0]["action"] == "serviced"
    assert lines[0]["summary"] == "Changed the oil"
    assert lines[0]["detail"] == "Next due 2027-01-01."


async def test_the_log_follows_a_component(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    item = await make_item(client, headers)
    component = (
        await client.post(
            "/api/components", json={"name": "Air filter"}, headers=headers
        )
    ).json()["data"]

    fitted = await client.post(
        f"/api/items/{item['id']}/components",
        json={"component_id": component["id"], "quantity": 2},
        headers=headers,
    )
    await client.delete(
        f"/api/item-components/{fitted.json()['data']['id']}", headers=headers
    )

    lines = await log_of(client, headers, item["id"])
    assert lines[0]["summary"] == "Air filter came off."
    assert lines[1]["summary"] == "2x Air filter was fitted."


async def test_the_whole_log_reads_newest_first(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    await make_item(client, headers, name="First")
    await make_item(client, headers, name="Second")

    response = await client.get("/api/activity?limit=2", headers=headers)
    lines = response.json()["data"]
    assert lines[0]["summary"] == "Second was added."
    assert lines[1]["summary"] == "First was added."


async def test_the_log_of_another_account_stays_hidden(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    item = await make_item(client, headers)
    other = await register(client)
    other_headers = await sign_in(client, other["email"])

    response = await client.get(
        f"/api/items/{item['id']}/activity", headers=other_headers
    )
    assert response.status_code == 404

    mine = await client.get("/api/activity", headers=other_headers)
    assert mine.json()["data"] == []


async def test_the_sync_carries_the_log(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    item = await make_item(client, headers)
    response = await client.get("/api/sync/changes", headers=headers)
    lines = response.json()["data"]["activity"]
    assert [line["entity_id"] for line in lines] == [item["id"]]
