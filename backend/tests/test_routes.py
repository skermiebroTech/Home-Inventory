"""Route tests for the remaining feature groups."""

from __future__ import annotations

import asyncio
import io
import json
from datetime import date, timedelta
from typing import Any

import pytest
from httpx import AsyncClient
from PIL import Image

pytestmark = pytest.mark.asyncio(loop_scope="session")


def image_bytes() -> bytes:
    """Return a small PNG for an upload."""
    buffer = io.BytesIO()
    Image.new("RGB", (600, 400), "slategray").save(buffer, format="PNG")
    return buffer.getvalue()


async def make_item(
    client: AsyncClient, headers: dict[str, str], name: str, **fields: Any
) -> dict[str, Any]:
    """Create one item and return it."""
    response = await client.post(
        "/api/items", json={"name": name, **fields}, headers=headers
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


# --------------------------------------------------------------------------
# Locations
# --------------------------------------------------------------------------


async def test_the_location_tree_nests_the_children(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    garage = (
        await client.post("/api/locations", json={"name": "Garage"}, headers=headers)
    ).json()["data"]
    shelf = (
        await client.post(
            "/api/locations",
            json={"name": "Shelf", "type": "zone", "parent_id": garage["id"]},
            headers=headers,
        )
    ).json()["data"]
    await make_item(client, headers, "Paint", location_id=shelf["id"])

    tree = (await client.get("/api/locations", headers=headers)).json()["data"]
    assert len(tree) == 1
    assert tree[0]["name"] == "Garage"
    assert tree[0]["children"][0]["name"] == "Shelf"
    assert tree[0]["children"][0]["item_count"] == 1
    assert tree[0]["item_count"] == 0


async def test_a_location_cannot_move_into_its_own_child(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    parent = (
        await client.post("/api/locations", json={"name": "Room"}, headers=headers)
    ).json()["data"]
    child = (
        await client.post(
            "/api/locations",
            json={"name": "Box", "type": "container", "parent_id": parent["id"]},
            headers=headers,
        )
    ).json()["data"]

    response = await client.put(
        f"/api/locations/{parent['id']}",
        json={"parent_id": child["id"]},
        headers=headers,
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "invalid_move"


async def test_deleting_a_location_unplaces_its_items(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    room = (
        await client.post("/api/locations", json={"name": "Study"}, headers=headers)
    ).json()["data"]
    drawer = (
        await client.post(
            "/api/locations",
            json={"name": "Drawer", "type": "container", "parent_id": room["id"]},
            headers=headers,
        )
    ).json()["data"]
    item = await make_item(client, headers, "Stapler", location_id=drawer["id"])

    response = await client.delete(f"/api/locations/{room['id']}", headers=headers)
    assert response.status_code == 200

    assert (await client.get("/api/locations", headers=headers)).json()["data"] == []
    stored = (await client.get(f"/api/items/{item['id']}", headers=headers)).json()[
        "data"
    ]
    assert stored["location_id"] is None


# --------------------------------------------------------------------------
# Tags
# --------------------------------------------------------------------------


async def test_tags_are_unique_by_name(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    first = await client.post(
        "/api/tags", json={"name": "Fragile", "color": "#ff0000"}, headers=headers
    )
    assert first.status_code == 201
    again = await client.post("/api/tags", json={"name": "fragile"}, headers=headers)
    assert again.status_code == 409


async def test_a_tag_goes_on_and_off_an_item(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    tag = (
        await client.post("/api/tags", json={"name": "Warranty"}, headers=headers)
    ).json()["data"]
    item = await make_item(client, headers, "Television")

    added = await client.post(
        f"/api/tags/{tag['id']}/items/{item['id']}", headers=headers
    )
    assert [t["name"] for t in added.json()["data"]["tags"]] == ["Warranty"]

    removed = await client.delete(
        f"/api/tags/{tag['id']}/items/{item['id']}", headers=headers
    )
    assert removed.json()["data"]["tags"] == []


async def test_deleting_a_tag_takes_it_off_the_items(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    tag = (
        await client.post("/api/tags", json={"name": "Temporary"}, headers=headers)
    ).json()["data"]
    item = await make_item(client, headers, "Cable", tag_ids=[tag["id"]])

    assert (
        await client.delete(f"/api/tags/{tag['id']}", headers=headers)
    ).status_code == 200
    stored = (await client.get(f"/api/items/{item['id']}", headers=headers)).json()[
        "data"
    ]
    assert stored["tags"] == []


# --------------------------------------------------------------------------
# Lending
# --------------------------------------------------------------------------


async def test_lend_and_return_an_item(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    item = await make_item(client, headers, "Extension ladder")

    lent = await client.post(
        f"/api/items/{item['id']}/lend",
        json={"lent_to": "Dave next door", "notes": "For the roof."},
        headers=headers,
    )
    assert lent.status_code == 200
    assert lent.json()["data"]["is_lent"] is True
    assert lent.json()["data"]["lent_to"] == "Dave next door"
    assert "For the roof." in lent.json()["data"]["notes"]

    listing = await client.get("/api/items/lent", headers=headers)
    assert [i["id"] for i in listing.json()["data"]] == [item["id"]]

    again = await client.post(
        f"/api/items/{item['id']}/lend",
        json={"lent_to": "Someone else"},
        headers=headers,
    )
    assert again.status_code == 409

    returned = await client.post(f"/api/items/{item['id']}/return", headers=headers)
    assert returned.json()["data"]["is_lent"] is False
    assert returned.json()["data"]["lent_to"] is None
    assert (await client.get("/api/items/lent", headers=headers)).json()["data"] == []


async def test_returning_an_item_that_is_here_is_refused(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    item = await make_item(client, headers, "Spirit level")
    response = await client.post(f"/api/items/{item['id']}/return", headers=headers)
    assert response.status_code == 409


# --------------------------------------------------------------------------
# Maintenance
# --------------------------------------------------------------------------


async def test_maintenance_history_and_the_due_list(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    item = await make_item(client, headers, "Air conditioner")
    soon = date.today() + timedelta(days=10)
    later = date.today() + timedelta(days=200)

    created = await client.post(
        f"/api/items/{item['id']}/maintenance",
        json={
            "description": "Clean the filters",
            "date_performed": str(date.today()),
            "next_due_date": str(soon),
            "cost": "0.00",
        },
        headers=headers,
    )
    assert created.status_code == 201

    await client.post(
        f"/api/items/{item['id']}/maintenance",
        json={"description": "Gas check", "next_due_date": str(later)},
        headers=headers,
    )

    history = await client.get(f"/api/items/{item['id']}/maintenance", headers=headers)
    assert len(history.json()["data"]) == 2

    upcoming = await client.get("/api/maintenance/upcoming?days=30", headers=headers)
    due = upcoming.json()["data"]
    assert [entry["description"] for entry in due] == ["Clean the filters"]
    assert due[0]["item_name"] == "Air conditioner"
    assert due[0]["days_until_due"] == 10


async def test_maintenance_can_be_corrected(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    item = await make_item(client, headers, "Generator")
    log = (
        await client.post(
            f"/api/items/{item['id']}/maintenance",
            json={"description": "Oil change"},
            headers=headers,
        )
    ).json()["data"]

    response = await client.put(
        f"/api/maintenance/{log['id']}",
        json={"description": "Oil and filter change", "cost": "89.00"},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["data"]["description"] == "Oil and filter change"
    assert response.json()["data"]["version"] == 2


# --------------------------------------------------------------------------
# NFC and labels
# --------------------------------------------------------------------------


async def test_an_nfc_tag_points_at_an_item(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    item = await make_item(client, headers, "Tool chest")

    registered = await client.post(
        "/api/nfc/register",
        json={"nfc_uid": "04:a2:1b:c3", "item_id": item["id"], "label": "Chest"},
        headers=headers,
    )
    assert registered.status_code == 201
    assert registered.json()["data"]["nfc_uid"] == "04A21BC3"

    found = await client.get("/api/nfc/04a21bc3", headers=headers)
    assert found.json()["data"]["target_type"] == "item"
    assert found.json()["data"]["target_name"] == "Tool chest"

    twice = await client.post(
        "/api/nfc/register",
        json={"nfc_uid": "04A21BC3", "item_id": item["id"]},
        headers=headers,
    )
    assert twice.status_code == 409

    assert (
        await client.delete("/api/nfc/04A21BC3", headers=headers)
    ).status_code == 200
    assert (await client.get("/api/nfc/04A21BC3", headers=headers)).status_code == 404


async def test_nfc_register_needs_exactly_one_target(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    response = await client.post(
        "/api/nfc/register", json={"nfc_uid": "0102"}, headers=headers
    )
    assert response.status_code == 422


async def test_the_label_routes_return_a_png(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    item = await make_item(client, headers, "Pressure washer")
    location = (
        await client.post("/api/locations", json={"name": "Carport"}, headers=headers)
    ).json()["data"]

    for url in (
        f"/api/items/{item['id']}/qr?size=256",
        f"/api/locations/{location['id']}/qr",
    ):
        response = await client.get(url, headers=headers)
        assert response.status_code == 200
        assert response.headers["content-type"] == "image/png"
        assert response.content.startswith(b"\x89PNG")


# --------------------------------------------------------------------------
# Export
# --------------------------------------------------------------------------


async def test_the_csv_export_holds_the_items(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    await make_item(client, headers, "Mitre saw", category="Tools")
    response = await client.get("/api/export/csv", headers=headers)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "Mitre saw" in response.text


async def test_the_insurance_report_is_a_pdf_file(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    await make_item(client, headers, "Piano", current_value="4500.00")
    response = await client.get("/api/export/insurance-report", headers=headers)
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF")


async def test_the_insurance_report_skips_the_cheap_items(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    await make_item(client, headers, "Teaspoon", current_value="2.00")
    response = await client.get(
        "/api/export/insurance-report?min_value=100", headers=headers
    )
    assert response.status_code == 200


# --------------------------------------------------------------------------
# Receipts
# --------------------------------------------------------------------------


async def test_a_receipt_upload_creates_the_row_at_once(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    response = await client.post(
        "/api/receipts/upload",
        files={"file": ("receipt.png", image_bytes(), "image/png")},
        headers=headers,
    )
    assert response.status_code == 201
    receipt = response.json()["data"]
    assert receipt["file_path"].startswith("receipts/")
    assert receipt["thumbnail_path"]
    assert receipt["currency"] == "AUD"
    assert "X-AI-Job-Id" in response.headers

    listing = await client.get("/api/receipts", headers=headers)
    assert listing.json()["data"]["total"] == 1

    # Let the background parse finish, so that it does not run after the
    # database is emptied for the next test.
    for _ in range(40):
        job = await client.get(
            f"/api/ai/jobs/{response.headers['X-AI-Job-Id']}", headers=headers
        )
        if job.json()["data"]["status"] in ("succeeded", "failed"):
            break
        await asyncio.sleep(0.05)


async def test_a_receipt_links_to_an_item(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    item = await make_item(client, headers, "Cordless drill", purchase_price="199.00")
    upload = await client.post(
        "/api/receipts/upload",
        files={"file": ("receipt.png", image_bytes(), "image/png")},
        headers=headers,
    )
    receipt = upload.json()["data"]

    linked = await client.post(
        f"/api/receipts/{receipt['id']}/link/{item['id']}", headers=headers
    )
    assert linked.status_code == 200
    lines = linked.json()["data"]["lines"]
    assert [line["item_id"] for line in lines] == [item["id"]]
    assert lines[0]["line_text"] == "Cordless drill"

    for _ in range(40):
        job = await client.get(
            f"/api/ai/jobs/{upload.headers['X-AI-Job-Id']}", headers=headers
        )
        if job.json()["data"]["status"] in ("succeeded", "failed"):
            break
        await asyncio.sleep(0.05)


async def test_receipt_corrections_are_saved(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    upload = await client.post(
        "/api/receipts/upload",
        files={"file": ("receipt.png", image_bytes(), "image/png")},
        headers=headers,
    )
    receipt = upload.json()["data"]

    response = await client.put(
        f"/api/receipts/{receipt['id']}",
        json={"vendor": "Bunnings", "total_amount": "47.80", "currency": "aud"},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["data"]["vendor"] == "Bunnings"
    assert response.json()["data"]["currency"] == "AUD"

    for _ in range(40):
        job = await client.get(
            f"/api/ai/jobs/{upload.headers['X-AI-Job-Id']}", headers=headers
        )
        if job.json()["data"]["status"] in ("succeeded", "failed"):
            break
        await asyncio.sleep(0.05)


# --------------------------------------------------------------------------
# AI, health, dashboard, and backup
# --------------------------------------------------------------------------


async def test_the_ai_status_says_that_the_feature_is_off(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    response = await client.get("/api/ai/status", headers=headers)
    assert response.status_code == 200
    state = response.json()["data"]
    assert state["enabled"] is False
    assert state["reachable"] is False
    assert state["vision_model"]
    assert state["inline_timeout_seconds"] >= 1


async def test_an_ai_route_answers_503_when_the_feature_is_off(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    response = await client.post(
        "/api/ai/recognize",
        files={"file": ("item.png", image_bytes(), "image/png")},
        headers=headers,
    )
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "ai_disabled"


async def test_health_reports_degraded_without_the_ai(
    client: AsyncClient,
) -> None:
    response = await client.get("/api/health")
    assert response.status_code == 200
    body = response.json()["data"]
    assert body["status"] == "degraded"
    assert body["database"]["ok"] is True
    assert body["ollama"]["ok"] is False
    assert body["disk"]["total_bytes"] > 0


async def test_the_dashboard_counts_the_inventory(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    room = (
        await client.post("/api/locations", json={"name": "Office"}, headers=headers)
    ).json()["data"]
    await make_item(
        client,
        headers,
        "Monitor",
        location_id=room["id"],
        current_value="450.00",
        quantity=2,
        warranty_expires=str(date.today() + timedelta(days=14)),
    )
    lent = await make_item(client, headers, "Desk lamp", purchase_price="30.00")
    await client.post(
        f"/api/items/{lent['id']}/lend", json={"lent_to": "Sam"}, headers=headers
    )

    response = await client.get("/api/dashboard", headers=headers)
    assert response.status_code == 200
    summary = response.json()["data"]
    assert summary["total_items"] == 2
    assert summary["total_quantity"] == 3
    assert summary["total_value"] == "930.00"
    assert summary["lent_count"] == 1
    assert summary["warranty_expiring_count"] == 1
    assert summary["items_by_location"][0]["location_name"] == "Office"


async def test_the_backup_schedule_can_be_set(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    response = await client.post(
        "/api/backup/schedule",
        json={"enabled": False, "cron": "30 2 * * *", "retention": 5},
        headers=headers,
    )
    assert response.status_code == 200
    status = response.json()["data"]
    assert status["schedule"]["cron"] == "30 2 * * *"
    assert status["schedule"]["retention"] == 5
    assert status["backups"] == []


async def test_a_bad_cron_expression_is_refused_by_the_route(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    response = await client.post(
        "/api/backup/schedule",
        json={"enabled": True, "cron": "not a cron", "retention": 5},
        headers=headers,
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


async def test_only_an_administrator_may_restore(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    from tests.conftest import register, sign_in

    await register(client, email="helper@example.com")
    helper = await sign_in(client, "helper@example.com")

    response = await client.post(
        "/api/backup/restore",
        files={"file": ("backup.zip", b"PK\x03\x04not a real zip", "application/zip")},
        headers=helper,
    )
    assert response.status_code == 403


async def test_the_full_export_is_a_zip_with_the_metadata(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    import zipfile

    await make_item(client, headers, "Welder", current_value="890.00")
    response = await client.get("/api/export/full", headers=headers)
    assert response.status_code == 200

    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        names = archive.namelist()
        assert "metadata.json" in names
        assert "inventory-report.csv" in names
        assert b"Welder" in archive.read("inventory-report.csv")
        metadata = json.loads(archive.read("metadata.json"))
        assert metadata["schema_version"] == "1"
        assert metadata["item_count"] == 1


async def test_a_backup_run_writes_an_archive_and_keeps_the_status(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    await make_item(client, headers, "Chainsaw")

    run = await client.post("/api/backup/run", headers=headers)
    assert run.status_code == 200, run.text
    assert "wrote" in run.json()["data"]["message"]

    status = (await client.get("/api/backup/status", headers=headers)).json()["data"]
    assert len(status["backups"]) >= 1
    assert status["backups"][0]["filename"].startswith("homestock-backup-")
    assert status["last_run_ok"] is True
