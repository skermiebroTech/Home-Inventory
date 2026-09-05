"""Tests for the cables section."""

from __future__ import annotations

from typing import Any

import pytest
from httpx import AsyncClient

from tests.conftest import register, sign_in

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def make_cable(
    client: AsyncClient, headers: dict[str, str], **fields: Any
) -> dict[str, Any]:
    """Add one cable."""
    body: dict[str, Any] = {
        "name": "USB-C to USB-C 2 m",
        "kind": "USB",
        "connector_a": "USB-C",
        "connector_b": "USB-C",
        "length_cm": 200,
        **fields,
    }
    response = await client.post("/api/cables", json=body, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()["data"]


async def test_add_a_cable(client: AsyncClient, headers: dict[str, str]) -> None:
    response = await client.post(
        "/api/cables",
        json={
            "name": "  Anker USB-C to HDMI  ",
            "kind": "Video",
            "connector_a": "USB-C",
            "connector_b": "HDMI",
            "length_cm": 180,
            "colour": "black",
            "brand": "Anker",
            "specification": "4K at 60 Hz",
            "quantity": 2,
            "price": "24.95",
            "notes": "In the desk drawer.",
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    cable = response.json()["data"]
    assert cable["name"] == "Anker USB-C to HDMI"
    assert cable["ends"] == "USB-C to HDMI"
    assert cable["length_label"] == "1.8 m"
    assert cable["total_value"] == "49.90"
    assert cable["version"] == 1


async def test_a_short_cable_reads_in_centimetres(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    cable = await make_cable(client, headers, name="Short lead", length_cm=30)
    assert cable["length_label"] == "30 cm"


async def test_a_round_length_drops_the_zeros(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    cable = await make_cable(client, headers, name="Long lead", length_cm=300)
    assert cable["length_label"] == "3 m"


async def test_one_end_is_enough_for_the_phrase(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    cable = await make_cable(
        client, headers, name="Kettle lead", connector_a="IEC C13", connector_b=None
    )
    assert cable["ends"] == "IEC C13"


async def test_a_cable_without_a_length_says_nothing(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    cable = await make_cable(client, headers, name="Unmeasured", length_cm=None)
    assert cable["length_label"] is None


async def test_the_search_matches_an_end(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    await make_cable(
        client,
        headers,
        name="Ethernet 5 m",
        kind="Network",
        connector_a="RJ45",
        connector_b="RJ45",
    )
    await make_cable(
        client,
        headers,
        name="Lightning lead",
        kind="USB",
        connector_a="USB-A",
        connector_b="Lightning",
    )

    response = await client.get("/api/cables?connector=lightning", headers=headers)
    assert response.status_code == 200
    rows = response.json()["data"]
    assert [row["name"] for row in rows] == ["Lightning lead"]


async def test_the_connector_filter_reads_both_ends(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    await make_cable(
        client, headers, name="A to C", connector_a="USB-A", connector_b="USB-C"
    )
    await make_cable(
        client, headers, name="C to A", connector_a="USB-C", connector_b="USB-A"
    )
    await make_cable(
        client,
        headers,
        name="HDMI to HDMI",
        kind="Video",
        connector_a="HDMI",
        connector_b="HDMI",
    )

    response = await client.get("/api/cables?connector=USB-C", headers=headers)
    names = sorted(row["name"] for row in response.json()["data"])
    assert names == ["A to C", "C to A"]


async def test_the_kind_filter_and_the_kind_list(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    await make_cable(client, headers, name="USB lead", kind="USB")
    await make_cable(client, headers, name="HDMI lead", kind="Video")
    await make_cable(client, headers, name="Power lead", kind="Power")

    response = await client.get("/api/cables?kind=Video", headers=headers)
    assert [row["name"] for row in response.json()["data"]] == ["HDMI lead"]

    kinds = await client.get("/api/cables/kinds", headers=headers)
    assert kinds.json()["data"] == ["Power", "USB", "Video"]


async def test_a_cable_names_its_place_and_its_device(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    place = await client.post(
        "/api/locations",
        json={"name": "Desk drawer", "kind": "container"},
        headers=headers,
    )
    item = await client.post(
        "/api/items", json={"name": "Brother printer"}, headers=headers
    )
    cable = await make_cable(
        client,
        headers,
        name="Printer lead",
        location_id=place.json()["data"]["id"],
        item_id=item.json()["data"]["id"],
    )
    assert cable["location_name"] == "Desk drawer"
    assert cable["item_name"] == "Brother printer"

    response = await client.get(
        f"/api/cables?item_id={item.json()['data']['id']}", headers=headers
    )
    assert [row["name"] for row in response.json()["data"]] == ["Printer lead"]


async def test_a_place_of_another_account_is_refused(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    other = await register(client)
    other_headers = await sign_in(client, other["email"])
    place = await client.post(
        "/api/locations",
        json={"name": "Their shed", "kind": "room"},
        headers=other_headers,
    )
    response = await client.post(
        "/api/cables",
        json={"name": "Lead", "location_id": place.json()["data"]["id"]},
        headers=headers,
    )
    assert response.status_code == 404


async def test_change_a_cable(client: AsyncClient, headers: dict[str, str]) -> None:
    cable = await make_cable(client, headers)
    response = await client.put(
        f"/api/cables/{cable['id']}",
        json={"quantity": 4, "colour": "white", "length_cm": 50},
        headers=headers,
    )
    assert response.status_code == 200
    changed = response.json()["data"]
    assert changed["quantity"] == 4
    assert changed["colour"] == "white"
    assert changed["length_label"] == "50 cm"
    assert changed["version"] == 2


async def test_a_count_below_zero_is_refused(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    cable = await make_cable(client, headers)
    response = await client.put(
        f"/api/cables/{cable['id']}", json={"quantity": -1}, headers=headers
    )
    assert response.status_code == 422


async def test_delete_a_cable(client: AsyncClient, headers: dict[str, str]) -> None:
    cable = await make_cable(client, headers)
    response = await client.delete(f"/api/cables/{cable['id']}", headers=headers)
    assert response.status_code == 200

    gone = await client.get(f"/api/cables/{cable['id']}", headers=headers)
    assert gone.status_code == 404

    rows = await client.get("/api/cables", headers=headers)
    assert rows.json()["data"] == []


async def test_a_cable_of_another_account_stays_hidden(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    await make_cable(client, headers, name="My lead")
    other = await register(client)
    other_headers = await sign_in(client, other["email"])

    response = await client.get("/api/cables", headers=other_headers)
    assert response.json()["data"] == []


async def test_the_sync_carries_the_cables(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    cable = await make_cable(client, headers, name="Sync lead")
    response = await client.get("/api/sync/changes", headers=headers)
    assert response.status_code == 200
    changes = response.json()["data"]
    assert [row["id"] for row in changes["cables"]] == [cable["id"]]
