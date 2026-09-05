"""Tests for the component catalogue, the fitted parts, and the spares."""

from __future__ import annotations

from typing import Any

import pytest
from httpx import AsyncClient

from tests.conftest import register, sign_in

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def make_component(
    client: AsyncClient, headers: dict[str, str], **fields: Any
) -> dict[str, Any]:
    """Add one entry to the catalogue."""
    body = {"name": "DeWalt DCB184 battery", **fields}
    response = await client.post("/api/components", json=body, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()["data"]


async def make_item(
    client: AsyncClient, headers: dict[str, str], name: str = "Drill"
) -> dict[str, Any]:
    """Create one item."""
    response = await client.post("/api/items", json={"name": name}, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()["data"]


# --------------------------------------------------------------------------
# The catalogue
# --------------------------------------------------------------------------


async def test_add_a_component_to_the_catalogue(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    response = await client.post(
        "/api/components",
        json={
            "name": "  DeWalt DCB184 battery  ",
            "brand": "DeWalt",
            "model_number": "DCB184",
            "category": "Batteries",
            "default_price": "119.00",
            "is_consumable": False,
        },
        headers=headers,
    )
    assert response.status_code == 201
    component = response.json()["data"]
    assert component["name"] == "DeWalt DCB184 battery"
    assert component["model_number"] == "DCB184"
    assert component["default_price"] == "119.00"
    assert component["is_consumable"] is False
    assert component["version"] == 1


async def test_the_catalogue_can_be_searched_and_filtered(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    await make_component(client, headers, brand="DeWalt", model_number="DCB184")
    await make_component(
        client, headers, name="Air filter", brand="Honda", is_consumable=True
    )

    by_model = await client.get("/api/components?q=DCB", headers=headers)
    assert [c["name"] for c in by_model.json()["data"]] == ["DeWalt DCB184 battery"]

    by_brand = await client.get("/api/components?q=honda", headers=headers)
    assert [c["name"] for c in by_brand.json()["data"]] == ["Air filter"]

    consumables = await client.get("/api/components?consumable=true", headers=headers)
    assert [c["name"] for c in consumables.json()["data"]] == ["Air filter"]


async def test_a_component_is_private_to_its_owner(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    component = await make_component(client, headers)

    await register(client, email="other-parts@example.com")
    other = await sign_in(client, "other-parts@example.com")

    assert (await client.get("/api/components", headers=other)).json()["data"] == []
    assert (
        await client.get(f"/api/components/{component['id']}", headers=other)
    ).status_code == 404


# --------------------------------------------------------------------------
# Fitted to an item
# --------------------------------------------------------------------------


async def test_fit_a_component_and_take_the_default_price(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    component = await make_component(client, headers, default_price="119.00")
    item = await make_item(client, headers)

    response = await client.post(
        f"/api/items/{item['id']}/components",
        json={"component_id": component["id"], "quantity": 2},
        headers=headers,
    )
    assert response.status_code == 201
    fitted = response.json()["data"]
    assert fitted["name"] == "DeWalt DCB184 battery"
    assert fitted["price"] is None
    # No price of its own, so the catalogue price applies.
    assert fitted["effective_price"] == "119.00"
    assert fitted["line_total"] == "238.00"


async def test_a_fitted_component_may_carry_its_own_price(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    component = await make_component(client, headers, default_price="119.00")
    item = await make_item(client, headers)

    response = await client.post(
        f"/api/items/{item['id']}/components",
        json={
            "component_id": component["id"],
            "price": "89.95",
            "serial_number": "BAT-77213",
            "notes": "Bought on sale. It holds less than the other one.",
        },
        headers=headers,
    )
    fitted = response.json()["data"]
    assert fitted["effective_price"] == "89.95"
    assert fitted["default_price"] == "119.00"
    assert fitted["serial_number"] == "BAT-77213"
    assert "holds less" in fitted["notes"]


async def test_the_item_lists_what_it_is_made_of(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    battery = await make_component(client, headers, default_price="119.00")
    chuck = await make_component(client, headers, name="Keyless chuck")
    item = await make_item(client, headers)

    for component_id in (battery["id"], chuck["id"]):
        await client.post(
            f"/api/items/{item['id']}/components",
            json={"component_id": component_id},
            headers=headers,
        )

    response = await client.get(f"/api/items/{item['id']}/components", headers=headers)
    assert response.status_code == 200
    names = [entry["name"] for entry in response.json()["data"]]
    assert names == ["DeWalt DCB184 battery", "Keyless chuck"]


async def test_change_and_remove_a_fitted_component(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    component = await make_component(client, headers)
    item = await make_item(client, headers)
    fitted = (
        await client.post(
            f"/api/items/{item['id']}/components",
            json={"component_id": component["id"]},
            headers=headers,
        )
    ).json()["data"]

    changed = await client.put(
        f"/api/item-components/{fitted['id']}",
        json={"quantity": 3, "price": "100.00", "notes": "Three of them."},
        headers=headers,
    )
    assert changed.status_code == 200
    assert changed.json()["data"]["quantity"] == 3
    assert changed.json()["data"]["line_total"] == "300.00"
    assert changed.json()["data"]["version"] == 2

    removed = await client.delete(
        f"/api/item-components/{fitted['id']}", headers=headers
    )
    assert removed.status_code == 200
    listing = await client.get(f"/api/items/{item['id']}/components", headers=headers)
    assert listing.json()["data"] == []


async def test_a_component_in_use_cannot_be_deleted(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    component = await make_component(client, headers)
    item = await make_item(client, headers)
    fitted = (
        await client.post(
            f"/api/items/{item['id']}/components",
            json={"component_id": component["id"]},
            headers=headers,
        )
    ).json()["data"]

    refused = await client.delete(f"/api/components/{component['id']}", headers=headers)
    assert refused.status_code == 409
    assert "still carry" in refused.json()["error"]["message"]

    await client.delete(f"/api/item-components/{fitted['id']}", headers=headers)
    allowed = await client.delete(f"/api/components/{component['id']}", headers=headers)
    assert allowed.status_code == 200


async def test_the_catalogue_entry_says_where_it_is_used(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    component = await make_component(client, headers)
    drill = await make_item(client, headers, "Drill")
    saw = await make_item(client, headers, "Saw")
    for item in (drill, saw):
        await client.post(
            f"/api/items/{item['id']}/components",
            json={"component_id": component["id"], "quantity": 2},
            headers=headers,
        )

    detail = await client.get(f"/api/components/{component['id']}", headers=headers)
    data = detail.json()["data"]
    assert data["fitted_count"] == 4
    assert sorted(use["item_name"] for use in data["fitted_to"]) == ["Drill", "Saw"]


# --------------------------------------------------------------------------
# Spares
# --------------------------------------------------------------------------


async def test_put_spares_on_the_shelf(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    component = await make_component(
        client, headers, name="Air filter", is_consumable=True, default_price="18.50"
    )
    response = await client.post(
        "/api/spares",
        json={
            "component_id": component["id"],
            "quantity": 4,
            "minimum_quantity": 2,
            "notes": "In the blue box.",
        },
        headers=headers,
    )
    assert response.status_code == 201
    spare = response.json()["data"]
    assert spare["quantity"] == 4
    assert spare["name"] == "Air filter"
    assert spare["is_consumable"] is True
    assert spare["effective_price"] == "18.50"
    assert spare["stock_value"] == "74.00"
    assert spare["is_low"] is False


async def test_the_same_component_in_the_same_place_is_one_row(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    component = await make_component(client, headers)
    await client.post(
        "/api/spares",
        json={"component_id": component["id"], "quantity": 1},
        headers=headers,
    )
    again = await client.post(
        "/api/spares",
        json={"component_id": component["id"], "quantity": 5},
        headers=headers,
    )
    assert again.status_code == 409
    assert "already has stock" in again.json()["error"]["message"]


async def test_the_low_stock_rows_come_first(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    plenty = await make_component(client, headers, name="Zip ties")
    running_out = await make_component(client, headers, name="Air filter")

    await client.post(
        "/api/spares",
        json={"component_id": plenty["id"], "quantity": 50, "minimum_quantity": 10},
        headers=headers,
    )
    await client.post(
        "/api/spares",
        json={"component_id": running_out["id"], "quantity": 1, "minimum_quantity": 2},
        headers=headers,
    )

    listing = await client.get("/api/spares", headers=headers)
    rows = listing.json()["data"]
    assert rows[0]["name"] == "Air filter"
    assert rows[0]["is_low"] is True
    assert rows[1]["is_low"] is False

    only_low = await client.get("/api/spares?low_only=true", headers=headers)
    assert [row["name"] for row in only_low.json()["data"]] == ["Air filter"]


async def test_using_a_spare_takes_it_off_the_shelf(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    component = await make_component(client, headers, name="Air filter")
    spare = (
        await client.post(
            "/api/spares",
            json={
                "component_id": component["id"],
                "quantity": 3,
                "minimum_quantity": 2,
            },
            headers=headers,
        )
    ).json()["data"]

    used = await client.post(
        f"/api/spares/{spare['id']}/use",
        json={"count": 1, "note": "Fitted to the mower."},
        headers=headers,
    )
    assert used.status_code == 200
    assert used.json()["data"]["quantity"] == 2
    assert used.json()["data"]["is_low"] is True
    assert "Fitted to the mower." in used.json()["data"]["notes"]

    # A negative count puts stock back.
    returned = await client.post(
        f"/api/spares/{spare['id']}/use", json={"count": -2}, headers=headers
    )
    assert returned.json()["data"]["quantity"] == 4


async def test_you_cannot_use_more_than_you_have(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    component = await make_component(client, headers)
    spare = (
        await client.post(
            "/api/spares",
            json={"component_id": component["id"], "quantity": 1},
            headers=headers,
        )
    ).json()["data"]

    response = await client.post(
        f"/api/spares/{spare['id']}/use", json={"count": 5}, headers=headers
    )
    assert response.status_code == 409
    assert "Only 1 left" in response.json()["error"]["message"]


async def test_deleting_a_component_takes_its_spares_with_it(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    component = await make_component(client, headers)
    await client.post(
        "/api/spares",
        json={"component_id": component["id"], "quantity": 2},
        headers=headers,
    )

    assert (
        await client.delete(f"/api/components/{component['id']}", headers=headers)
    ).status_code == 200
    assert (await client.get("/api/spares", headers=headers)).json()["data"] == []


async def test_a_spare_can_name_the_place_that_holds_it(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    location = (
        await client.post(
            "/api/locations", json={"name": "Parts drawer"}, headers=headers
        )
    ).json()["data"]
    component = await make_component(client, headers)

    spare = (
        await client.post(
            "/api/spares",
            json={
                "component_id": component["id"],
                "quantity": 6,
                "location_id": location["id"],
            },
            headers=headers,
        )
    ).json()["data"]
    assert spare["location_name"] == "Parts drawer"


# --------------------------------------------------------------------------
# Sync
# --------------------------------------------------------------------------


async def test_the_phone_receives_the_components_and_the_spares(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    component = await make_component(client, headers, default_price="119.00")
    item = await make_item(client, headers)
    await client.post(
        f"/api/items/{item['id']}/components",
        json={"component_id": component["id"], "notes": "The one with the tape on it."},
        headers=headers,
    )
    await client.post(
        "/api/spares",
        json={"component_id": component["id"], "quantity": 2},
        headers=headers,
    )

    changes = (await client.get("/api/sync/changes", headers=headers)).json()["data"]
    assert [c["name"] for c in changes["components"]] == ["DeWalt DCB184 battery"]
    assert len(changes["item_components"]) == 1
    assert changes["item_components"][0]["notes"] == "The one with the tape on it."
    assert changes["spares"][0]["quantity"] == 2
