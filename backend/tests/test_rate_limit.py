"""The sign in routes refuse a password guessing run."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient

from tests.conftest import register

pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest.fixture
def strict_limit() -> object:
    """Turn the limit on, and set it low, for one test."""
    from app.config import settings
    from app.utils.rate_limit import limiter

    original = settings.rate_limit_auth
    settings.rate_limit_auth = "3/minute"
    limiter.enabled = True
    limiter.reset()
    yield
    limiter.enabled = False
    limiter.reset()
    settings.rate_limit_auth = original


async def test_repeated_sign_in_attempts_are_refused(
    client: AsyncClient, strict_limit: object
) -> None:
    await register(client, email="target@example.com")

    codes: list[int] = []
    for _ in range(5):
        response = await client.post(
            "/api/auth/login",
            json={"email": "target@example.com", "password": "wrong password"},
        )
        codes.append(response.status_code)

    assert codes[:3] == [401, 401, 401]
    assert 429 in codes

    refused = await client.post(
        "/api/auth/login",
        json={"email": "target@example.com", "password": "wrong password"},
    )
    assert refused.status_code == 429
    body = refused.json()
    assert body["data"] is None
    assert body["error"]["code"] == "rate_limited"


async def test_the_limit_does_not_touch_the_signed_in_routes(
    client: AsyncClient, headers: dict[str, str], strict_limit: object
) -> None:
    # Ten reads in a row must all pass. Only the sign in routes are limited.
    for _ in range(10):
        response = await client.get("/api/items", headers=headers)
        assert response.status_code == 200


async def test_registration_is_limited_as_well(
    client: AsyncClient, strict_limit: object
) -> None:
    codes: list[int] = []
    for _ in range(5):
        response = await client.post(
            "/api/auth/register",
            json={
                "email": f"{uuid.uuid4().hex[:8]}@example.com",
                "name": "Someone",
                "password": "correct horse battery",
            },
        )
        codes.append(response.status_code)
    assert 429 in codes
