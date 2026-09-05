"""Tests for registration, sign in, token refresh, and the JWT dependency."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.conftest import register, sign_in

pytestmark = pytest.mark.asyncio(loop_scope="session")

PASSWORD = "correct horse battery"


async def test_first_account_becomes_the_admin(client: AsyncClient) -> None:
    response = await client.post(
        "/api/auth/register",
        json={"email": "first@example.com", "name": "First", "password": PASSWORD},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["error"] is None
    assert body["data"]["role"] == "admin"
    assert body["data"]["email"] == "first@example.com"
    assert "password_hash" not in body["data"]


async def test_second_account_is_a_plain_user(client: AsyncClient) -> None:
    await register(client, email="first@example.com")
    second = await register(client, email="second@example.com")
    assert second["role"] == "user"


async def test_register_refuses_a_repeated_email(client: AsyncClient) -> None:
    await register(client, email="taken@example.com")
    response = await client.post(
        "/api/auth/register",
        json={"email": "TAKEN@example.com", "name": "Copy", "password": PASSWORD},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"
    assert response.json()["data"] is None


async def test_register_refuses_a_short_password(client: AsyncClient) -> None:
    response = await client.post(
        "/api/auth/register",
        json={"email": "short@example.com", "name": "Short", "password": "abc"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


async def test_login_returns_a_token_pair(client: AsyncClient) -> None:
    await register(client, email="signin@example.com")
    response = await client.post(
        "/api/auth/login",
        json={"email": "signin@example.com", "password": PASSWORD},
    )
    assert response.status_code == 200
    tokens = response.json()["data"]
    assert tokens["token_type"] == "bearer"
    assert tokens["expires_in"] == 30 * 60
    assert tokens["access_token"] != tokens["refresh_token"]


async def test_login_ignores_the_letter_case_of_the_email(
    client: AsyncClient,
) -> None:
    await register(client, email="case@example.com")
    response = await client.post(
        "/api/auth/login",
        json={"email": "CASE@Example.Com", "password": PASSWORD},
    )
    assert response.status_code == 200


async def test_login_refuses_a_wrong_password(client: AsyncClient) -> None:
    await register(client, email="wrong@example.com")
    response = await client.post(
        "/api/auth/login",
        json={"email": "wrong@example.com", "password": "not the password"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


async def test_login_refuses_an_unknown_email(client: AsyncClient) -> None:
    response = await client.post(
        "/api/auth/login",
        json={"email": "nobody@example.com", "password": PASSWORD},
    )
    assert response.status_code == 401
    # The message must not say whether the account exists.
    assert "password is wrong" in response.json()["error"]["message"]


async def test_me_returns_the_signed_in_user(client: AsyncClient) -> None:
    await register(client, email="me@example.com")
    headers = await sign_in(client, "me@example.com")
    response = await client.get("/api/auth/me", headers=headers)
    assert response.status_code == 200
    assert response.json()["data"]["email"] == "me@example.com"


async def test_me_needs_a_token(client: AsyncClient) -> None:
    response = await client.get("/api/auth/me")
    assert response.status_code == 401
    assert response.json()["data"] is None


async def test_me_refuses_a_damaged_token(client: AsyncClient) -> None:
    response = await client.get(
        "/api/auth/me", headers={"Authorization": "Bearer not.a.token"}
    )
    assert response.status_code == 401


async def test_me_refuses_a_refresh_token(client: AsyncClient) -> None:
    await register(client, email="swap@example.com")
    login = await client.post(
        "/api/auth/login",
        json={"email": "swap@example.com", "password": PASSWORD},
    )
    refresh_token = login.json()["data"]["refresh_token"]
    response = await client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {refresh_token}"}
    )
    assert response.status_code == 401
    assert "access token" in response.json()["error"]["message"]


async def test_refresh_returns_a_new_pair(client: AsyncClient) -> None:
    await register(client, email="refresh@example.com")
    login = await client.post(
        "/api/auth/login",
        json={"email": "refresh@example.com", "password": PASSWORD},
    )
    refresh_token = login.json()["data"]["refresh_token"]

    response = await client.post(
        "/api/auth/refresh", json={"refresh_token": refresh_token}
    )
    assert response.status_code == 200
    pair = response.json()["data"]

    me = await client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {pair['access_token']}"},
    )
    assert me.status_code == 200
    assert me.json()["data"]["email"] == "refresh@example.com"


async def test_refresh_refuses_an_access_token(client: AsyncClient) -> None:
    await register(client, email="mixup@example.com")
    login = await client.post(
        "/api/auth/login",
        json={"email": "mixup@example.com", "password": PASSWORD},
    )
    access_token = login.json()["data"]["access_token"]
    response = await client.post(
        "/api/auth/refresh", json={"refresh_token": access_token}
    )
    assert response.status_code == 401


async def test_a_turned_off_account_cannot_sign_in(client: AsyncClient) -> None:
    from sqlalchemy import select

    from app.database import SessionLocal
    from app.models.user import User

    await register(client, email="off@example.com")
    async with SessionLocal() as session:
        user = (
            await session.execute(select(User).where(User.email == "off@example.com"))
        ).scalar_one()
        user.is_active = False
        await session.commit()

    response = await client.post(
        "/api/auth/login",
        json={"email": "off@example.com", "password": PASSWORD},
    )
    assert response.status_code == 401
    assert "turned off" in response.json()["error"]["message"]
