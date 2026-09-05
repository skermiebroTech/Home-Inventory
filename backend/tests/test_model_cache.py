"""Tests for the phone models that the server keeps."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.services import model_cache
from tests.conftest import register, sign_in

pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest.fixture(autouse=True)
def _clean() -> None:
    """No model is on the server when a test starts."""
    for model in model_cache.MODELS:
        model_cache.forget(model)


async def test_the_list_names_every_model(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    response = await client.get("/api/models", headers=headers)
    assert response.status_code == 200
    rows = response.json()["data"]

    assert [row["id"] for row in rows] == [model.id for model in model_cache.MODELS]
    first = rows[0]
    assert first["ready"] is False
    assert first["cached_bytes"] == 0
    assert first["bytes"] > 0
    # The phone reads both places from here: the local one and the far one.
    assert first["files"][0]["path"].startswith("/models/")
    assert first["files"][0]["origin"].startswith("https://")


async def test_a_stranger_gets_nothing(client: AsyncClient) -> None:
    response = await client.get("/api/models")
    assert response.status_code == 401


async def test_an_unknown_model_answers_404(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    assert (
        await client.post("/api/models/no-such-model/fetch", headers=headers)
    ).status_code == 404
    assert (
        await client.delete("/api/models/no-such-model", headers=headers)
    ).status_code == 404


async def test_a_fetch_puts_the_files_where_the_phone_asks(
    client: AsyncClient, headers: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The fetch is stubbed. A test must not pull a gigabyte."""
    model = model_cache.MODELS[1]

    async def fake_fetch_file(_client, _url, target, state) -> None:  # type: ignore[no-untyped-def]
        target.write_bytes(b"weights")
        state.written += 7

    monkeypatch.setattr(model_cache, "_fetch_file", fake_fetch_file)
    # The real sizes would make "ready" false for a seven byte file.
    monkeypatch.setattr(
        model_cache, "is_ready", lambda one: model_cache.bytes_here(one) > 0
    )

    response = await client.post(f"/api/models/{model.id}/fetch", headers=headers)
    assert response.status_code == 202

    state = model_cache.state_of(model.id)
    assert state and state.task
    await state.task
    assert state.error is None

    for one in model.files:
        path = model_cache.path_of(model, one)
        assert path.exists()
        assert path.name == f"{model.id}-{one.part}.gguf"

    listed = await client.get("/api/models", headers=headers)
    row = next(r for r in listed.json()["data"] if r["id"] == model.id)
    assert row["cached_bytes"] == 14
    assert row["fetching"] is False


async def test_delete_gives_the_space_back(
    client: AsyncClient, headers: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    model = model_cache.MODELS[1]

    async def fake_fetch_file(_client, _url, target, state) -> None:  # type: ignore[no-untyped-def]
        target.write_bytes(b"weights")
        state.written += 7

    monkeypatch.setattr(model_cache, "_fetch_file", fake_fetch_file)
    await client.post(f"/api/models/{model.id}/fetch", headers=headers)
    state = model_cache.state_of(model.id)
    assert state and state.task
    await state.task

    response = await client.delete(f"/api/models/{model.id}", headers=headers)
    assert response.status_code == 200
    assert model_cache.bytes_here(model) == 0


async def test_another_account_sees_the_same_models(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    """The weights are not somebody's data. Every account reads one copy."""
    other = await register(client)
    other_headers = await sign_in(client, other["email"])

    mine = await client.get("/api/models", headers=headers)
    theirs = await client.get("/api/models", headers=other_headers)
    assert [row["id"] for row in mine.json()["data"]] == [
        row["id"] for row in theirs.json()["data"]
    ]
