"""Tests for the delta sync endpoints that the mobile application uses."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from httpx import AsyncClient

from tests.conftest import register, sign_in

pytestmark = pytest.mark.asyncio(loop_scope="session")


def now() -> str:
    """Return the current time as the client would send it."""
    return datetime.now(UTC).isoformat()


async def pull(
    client: AsyncClient,
    headers: dict[str, str],
    since: str | None = None,
    **params: Any,
) -> dict[str, Any]:
    """Call GET /api/sync/changes and return the payload."""
    query: dict[str, Any] = dict(params)
    if since:
        query["since"] = since
    response = await client.get("/api/sync/changes", params=query, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()["data"]


async def push(
    client: AsyncClient, headers: dict[str, str], *changes: dict[str, Any]
) -> dict[str, Any]:
    """Call POST /api/sync/push and return the payload."""
    response = await client.post(
        "/api/sync/push", json={"changes": list(changes)}, headers=headers
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]


async def make_item(
    client: AsyncClient, headers: dict[str, str], name: str, **fields: Any
) -> dict[str, Any]:
    """Create one item through the normal route."""
    response = await client.post(
        "/api/items", json={"name": name, **fields}, headers=headers
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


# --------------------------------------------------------------------------
# Pull
# --------------------------------------------------------------------------


async def test_first_sync_returns_everything(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    await client.post("/api/locations", json={"name": "Shed"}, headers=headers)
    await client.post("/api/tags", json={"name": "Outdoor"}, headers=headers)
    await make_item(client, headers, "Wheelbarrow")

    changes = await pull(client, headers)
    assert changes["since"] is None
    assert [i["name"] for i in changes["items"]] == ["Wheelbarrow"]
    assert [i["name"] for i in changes["locations"]] == ["Shed"]
    assert [t["name"] for t in changes["tags"]] == ["Outdoor"]
    assert changes["has_more"] is False
    assert changes["server_time"]


async def test_sync_returns_only_what_changed(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    await make_item(client, headers, "Old item")
    first = await pull(client, headers)

    await make_item(client, headers, "New item")
    second = await pull(client, headers, since=first["server_time"])

    assert [i["name"] for i in second["items"]] == ["New item"]
    assert second["locations"] == []


async def test_an_edit_appears_in_the_next_sync(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    item = await make_item(client, headers, "Ladder")
    marker = (await pull(client, headers))["server_time"]

    await client.put(
        f"/api/items/{item['id']}", json={"name": "Tall ladder"}, headers=headers
    )
    changes = await pull(client, headers, since=marker)
    assert [i["name"] for i in changes["items"]] == ["Tall ladder"]
    assert changes["items"][0]["version"] == 2


async def test_a_deleted_item_arrives_as_a_tombstone(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    item = await make_item(client, headers, "Rusty saw")
    marker = (await pull(client, headers))["server_time"]

    await client.delete(f"/api/items/{item['id']}", headers=headers)

    changes = await pull(client, headers, since=marker)
    assert changes["items"] == []
    assert changes["deleted"]["item"] == [item["id"]]


async def test_sync_reports_more_pages(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    for index in range(4):
        await make_item(client, headers, f"Item {index}")
    changes = await pull(client, headers, limit=2)
    assert changes["has_more"] is True
    assert len(changes["items"]) == 2


async def test_sync_shows_only_the_rows_of_the_signed_in_account(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    await make_item(client, headers, "Mine")

    await register(client, email="other@example.com")
    other = await sign_in(client, "other@example.com")
    await make_item(client, other, "Theirs")

    assert [i["name"] for i in (await pull(client, headers))["items"]] == ["Mine"]
    assert [i["name"] for i in (await pull(client, other))["items"]] == ["Theirs"]


async def test_sync_needs_a_token(client: AsyncClient) -> None:
    response = await client.get("/api/sync/changes")
    assert response.status_code == 401


# --------------------------------------------------------------------------
# Push
# --------------------------------------------------------------------------


async def test_push_creates_a_row_with_the_client_id(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    new_id = str(uuid.uuid4())
    result = await push(
        client,
        headers,
        {
            "entity": "item",
            "op": "create",
            "id": new_id,
            "payload": {"name": "Offline drill", "category": "Tools", "quantity": 3},
            "client_updated_at": now(),
        },
    )
    assert result["applied"] == 1
    assert result["rejected"] == 0

    stored = await client.get(f"/api/items/{new_id}", headers=headers)
    assert stored.status_code == 200
    assert stored.json()["data"]["name"] == "Offline drill"
    assert stored.json()["data"]["quantity"] == 3


async def test_push_repeats_a_create_without_making_a_second_row(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    new_id = str(uuid.uuid4())
    change = {
        "entity": "item",
        "op": "create",
        "id": new_id,
        "payload": {"name": "Sent twice"},
        "client_updated_at": now(),
    }
    await push(client, headers, change)
    await push(client, headers, {**change, "base_version": 1})

    listing = await client.get("/api/items", headers=headers)
    assert listing.json()["data"]["total"] == 1


async def test_push_updates_a_row(client: AsyncClient, headers: dict[str, str]) -> None:
    item = await make_item(client, headers, "Bench grinder")
    result = await push(
        client,
        headers,
        {
            "entity": "item",
            "op": "update",
            "id": item["id"],
            "base_version": item["version"],
            "payload": {"notes": "The guard is loose.", "condition": "fair"},
            "client_updated_at": now(),
        },
    )
    assert result["applied"] == 1

    stored = (await client.get(f"/api/items/{item['id']}", headers=headers)).json()[
        "data"
    ]
    assert stored["notes"] == "The guard is loose."
    assert stored["condition"] == "fair"
    assert stored["version"] == item["version"] + 1


async def test_the_server_wins_a_conflict(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    item = await make_item(client, headers, "Contested item")

    # Somebody edits the item on the web interface.
    await client.put(
        f"/api/items/{item['id']}", json={"name": "Server name"}, headers=headers
    )

    # The phone was offline and still holds the first version.
    result = await push(
        client,
        headers,
        {
            "entity": "item",
            "op": "update",
            "id": item["id"],
            "base_version": item["version"],
            "payload": {"name": "Phone name"},
            "client_updated_at": now(),
        },
    )

    assert result["applied"] == 0
    assert result["rejected"] == 1
    conflict = result["conflicts"][0]
    assert conflict["entity"] == "item"
    assert conflict["id"] == item["id"]
    assert conflict["server_version"] == 2

    stored = (await client.get(f"/api/items/{item['id']}", headers=headers)).json()[
        "data"
    ]
    assert stored["name"] == "Server name"


async def test_a_stale_timestamp_also_loses(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    item = await make_item(client, headers, "Timestamp test")
    stale = "2020-01-01T00:00:00+00:00"

    result = await push(
        client,
        headers,
        {
            "entity": "item",
            "op": "update",
            "id": item["id"],
            "payload": {"name": "Late edit"},
            "client_updated_at": stale,
        },
    )
    assert result["applied"] == 0
    assert result["conflicts"][0]["reason"]


async def test_push_deletes_a_row(client: AsyncClient, headers: dict[str, str]) -> None:
    item = await make_item(client, headers, "To remove")
    result = await push(
        client,
        headers,
        {
            "entity": "item",
            "op": "delete",
            "id": item["id"],
            "base_version": item["version"],
            "client_updated_at": now(),
        },
    )
    assert result["applied"] == 1
    assert (
        await client.get(f"/api/items/{item['id']}", headers=headers)
    ).status_code == 404


async def test_a_repeated_delete_is_not_an_error(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    result = await push(
        client,
        headers,
        {
            "entity": "item",
            "op": "delete",
            "id": str(uuid.uuid4()),
            "client_updated_at": now(),
        },
    )
    assert result["applied"] == 1
    assert result["rejected"] == 0


async def test_push_cannot_touch_another_account(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    mine = await make_item(client, headers, "Mine only")

    await register(client, email="thief@example.com")
    thief = await sign_in(client, "thief@example.com")

    result = await push(
        client,
        thief,
        {
            "entity": "item",
            "op": "update",
            "id": mine["id"],
            "payload": {"name": "Taken"},
            "client_updated_at": now(),
        },
    )
    assert result["applied"] == 0
    assert result["rejected"] == 1

    stored = (await client.get(f"/api/items/{mine['id']}", headers=headers)).json()[
        "data"
    ]
    assert stored["name"] == "Mine only"


async def test_push_cannot_add_a_child_row_to_another_account(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    mine = await make_item(client, headers, "My machine")

    await register(client, email="stranger@example.com")
    stranger = await sign_in(client, "stranger@example.com")

    result = await push(
        client,
        stranger,
        {
            "entity": "maintenance",
            "op": "create",
            "id": str(uuid.uuid4()),
            "payload": {"item_id": mine["id"], "description": "Sneaky service"},
            "client_updated_at": now(),
        },
    )
    assert result["applied"] == 0
    assert result["rejected"] == 1

    logs = await client.get(f"/api/items/{mine['id']}/maintenance", headers=headers)
    assert logs.json()["data"] == []


async def test_push_reports_a_bad_change_without_stopping_the_batch(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    good_id = str(uuid.uuid4())
    result = await push(
        client,
        headers,
        {
            "entity": "item",
            "op": "create",
            "id": good_id,
            "payload": {"name": "Good row"},
            "client_updated_at": now(),
        },
        {
            "entity": "item",
            "op": "create",
            "id": str(uuid.uuid4()),
            "payload": {"name": "Bad row", "purchase_price": "not a number"},
            "client_updated_at": now(),
        },
    )
    assert result["applied"] == 1
    assert result["rejected"] == 1
    assert (
        await client.get(f"/api/items/{good_id}", headers=headers)
    ).status_code == 200


async def test_push_child_rows_of_the_own_account(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    item = await make_item(client, headers, "Lawn mower")
    result = await push(
        client,
        headers,
        {
            "entity": "maintenance",
            "op": "create",
            "id": str(uuid.uuid4()),
            "payload": {
                "item_id": item["id"],
                "description": "Changed the oil",
                "date_performed": "2026-03-01",
                "next_due_date": "2027-03-01",
                "cost": "24.50",
            },
            "client_updated_at": now(),
        },
    )
    assert result["applied"] == 1

    logs = (
        await client.get(f"/api/items/{item['id']}/maintenance", headers=headers)
    ).json()["data"]
    assert logs[0]["description"] == "Changed the oil"
    assert logs[0]["cost"] == "24.50"


async def test_a_pushed_change_comes_back_in_the_next_pull(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    marker = (await pull(client, headers))["server_time"]
    new_id = str(uuid.uuid4())
    await push(
        client,
        headers,
        {
            "entity": "item",
            "op": "create",
            "id": new_id,
            "payload": {"name": "Round trip"},
            "client_updated_at": now(),
        },
    )
    changes = await pull(client, headers, since=marker)
    assert [i["id"] for i in changes["items"]] == [new_id]
