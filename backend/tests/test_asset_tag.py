"""Tests for the asset tag: the number on the sticker."""

from __future__ import annotations

from typing import Any

import pytest
from httpx import AsyncClient

from app.utils.qr import item_qr_payload
from tests.conftest import register, sign_in

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def make_item(
    client: AsyncClient, headers: dict[str, str], name: str = "Drill"
) -> dict[str, Any]:
    response = await client.post("/api/items", json={"name": name}, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()["data"]


async def test_a_new_item_carries_a_seven_digit_tag(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    item = await make_item(client, headers)
    assert len(item["asset_tag"]) == 7
    assert item["asset_tag"].isdigit()


async def test_each_item_takes_the_next_number(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    first = await make_item(client, headers, "First")
    second = await make_item(client, headers, "Second")
    assert int(second["asset_tag"]) == int(first["asset_tag"]) + 1


async def test_two_accounts_never_share_a_number(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    mine = await make_item(client, headers, "Mine")
    other = await register(client)
    other_headers = await sign_in(client, other["email"])
    theirs = await make_item(client, other_headers, "Theirs")
    assert mine["asset_tag"] != theirs["asset_tag"]


async def test_the_tag_finds_the_item(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    item = await make_item(client, headers, "Mower")
    response = await client.get(
        f"/api/items/by-tag/{item['asset_tag']}", headers=headers
    )
    assert response.status_code == 200
    assert response.json()["data"]["id"] == item["id"]


async def test_a_short_number_is_padded_back(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    item = await make_item(client, headers, "Mower")
    typed = str(int(item["asset_tag"]))  # what a person reads off the sticker

    response = await client.get(f"/api/items/by-tag/{typed}", headers=headers)
    assert response.status_code == 200
    assert response.json()["data"]["id"] == item["id"]


async def test_an_unknown_tag_answers_404(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    response = await client.get("/api/items/by-tag/9999999", headers=headers)
    assert response.status_code == 404


async def test_the_tag_of_another_account_stays_hidden(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    item = await make_item(client, headers, "Mine")
    other = await register(client)
    other_headers = await sign_in(client, other["email"])

    response = await client.get(
        f"/api/items/by-tag/{item['asset_tag']}", headers=other_headers
    )
    assert response.status_code == 404


async def test_the_search_finds_a_tag(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    item = await make_item(client, headers, "Mower")
    response = await client.get(
        f"/api/items?q={int(item['asset_tag'])}", headers=headers
    )
    assert [row["id"] for row in response.json()["data"]["items"]] == [item["id"]]


async def test_the_label_holds_the_short_address(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    item = await make_item(client, headers)
    response = await client.get(f"/api/items/{item['id']}/qr", headers=headers)
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"

    # The picture is a picture, so the payload is checked on its own.
    payload = item_qr_payload(item["asset_tag"], "http://tower:7850")
    assert payload == f"http://tower:7850/a/{item['asset_tag']}"
    assert len(payload) < len(f"http://tower:7850/items/{item['id']}")


async def test_the_sync_carries_the_tag(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    item = await make_item(client, headers)
    response = await client.get("/api/sync/changes", headers=headers)
    rows = response.json()["data"]["items"]
    assert [row["asset_tag"] for row in rows] == [item["asset_tag"]]
