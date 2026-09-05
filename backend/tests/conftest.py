"""Test fixtures.

The models use PostgreSQL types: a UUID primary key, JSONB, and a generated
``tsvector`` column. SQLite cannot hold those, so the tests run against a real
PostgreSQL server.

Set ``HS_TEST_DATABASE_URL`` to use a server that is already running. If that
variable is absent, the fixtures start a private server through ``pgserver``,
which ships its own PostgreSQL binaries and needs no Docker.

Every environment variable is set here, at import time, because
``app/config.py`` reads the environment once when it is imported.
"""

from __future__ import annotations

import os
import tempfile
import uuid
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

TEST_ROOT = Path(tempfile.mkdtemp(prefix="homestock-test-"))
TEST_DATABASE = "homestock_test"

_server: Any = None


def _database_url() -> str:
    """Return the async database URL that the tests run against."""
    configured = os.getenv("HS_TEST_DATABASE_URL")
    if configured:
        return configured

    import pgserver

    global _server
    _server = pgserver.get_server(TEST_ROOT / "pgdata")
    existing = _server.psql(
        f"SELECT 1 FROM pg_database WHERE datname = '{TEST_DATABASE}'"
    )
    if "1" not in existing:
        _server.psql(f"CREATE DATABASE {TEST_DATABASE}")
    uri = _server.get_uri(database=TEST_DATABASE)
    return uri.replace("postgresql://", "postgresql+asyncpg://")


os.environ.update(
    {
        "HS_SECRET_KEY": "test-secret-key-for-the-homestock-suite-0123456789",
        "HS_ACCESS_TOKEN_EXPIRE_MINUTES": "30",
        "HS_REFRESH_TOKEN_EXPIRE_DAYS": "7",
        "HS_DATA_DIR": str(TEST_ROOT),
        "HS_UPLOAD_DIR": str(TEST_ROOT / "uploads"),
        "HS_BACKUP_DIR": str(TEST_ROOT / "backups"),
        "HS_CONFIG_DIR": str(TEST_ROOT / "config"),
        "HS_STATIC_DIR": str(TEST_ROOT / "static"),
        "HS_RUN_MIGRATIONS_ON_START": "false",
        # No Ollama runs during a test. Every AI route must answer 503 instead
        # of waiting for a connection that never opens.
        "HS_AI_ENABLED": "false",
        "HS_BACKUP_ENABLED": "false",
        "HS_SERVE_MEDIA": "false",
        # The suite signs in many times in one second. The limit stays off,
        # and test_rate_limit.py turns it on for its own check.
        "HS_RATE_LIMIT_AUTH": "",
    }
)
for name in ("uploads", "backups", "config"):
    (TEST_ROOT / name).mkdir(parents=True, exist_ok=True)
os.environ["HS_DATABASE_URL"] = _database_url()


def pytest_sessionfinish(session: Any, exitstatus: int) -> None:
    """Stop the private database and remove its files.

    A PostgreSQL data directory holds tens of megabytes. Without this hook,
    every run would leave another copy in the temporary directory.
    """
    import shutil

    if _server is not None:
        _server.cleanup()
    shutil.rmtree(TEST_ROOT, ignore_errors=True)


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def _schema() -> AsyncIterator[None]:
    """Create the tables once for the whole run."""
    from app.database import engine
    from app.models import Base

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


@pytest_asyncio.fixture(loop_scope="session")
async def clean_database(_schema: None) -> AsyncIterator[None]:
    """Empty every table before each test."""
    from sqlalchemy import text

    from app.database import engine
    from app.models import Base

    tables = ", ".join(f'"{name}"' for name in Base.metadata.tables)
    async with engine.begin() as connection:
        await connection.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
    yield


@pytest_asyncio.fixture(loop_scope="session")
async def client(clean_database: None) -> AsyncIterator[AsyncClient]:
    """Return an HTTP client that talks to the application in this process."""
    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://homestock.test"
    ) as http:
        yield http


async def register(
    http: AsyncClient,
    *,
    email: str | None = None,
    password: str = "correct horse battery",
    name: str = "Test Person",
) -> dict[str, Any]:
    """Create one account and return the user record."""
    address = email or f"user-{uuid.uuid4().hex[:8]}@example.com"
    response = await http.post(
        "/api/auth/register",
        json={"email": address, "name": name, "password": password},
    )
    assert response.status_code == 201, response.text
    user = response.json()["data"]
    user["password"] = address and password
    user["email"] = address
    return user


async def sign_in(
    http: AsyncClient, email: str, password: str = "correct horse battery"
) -> dict[str, str]:
    """Sign in and return the bearer header."""
    response = await http.post(
        "/api/auth/login", json={"email": email, "password": password}
    )
    assert response.status_code == 200, response.text
    tokens = response.json()["data"]
    return {"Authorization": f"Bearer {tokens['access_token']}"}


@pytest_asyncio.fixture(loop_scope="session")
async def account(client: AsyncClient) -> dict[str, Any]:
    """Register the first account and return it with its bearer header."""
    user = await register(client, email="owner@example.com")
    user["headers"] = await sign_in(client, "owner@example.com")
    return user


@pytest_asyncio.fixture(loop_scope="session")
async def headers(account: dict[str, Any]) -> dict[str, str]:
    """Return the bearer header of the signed in account."""
    return account["headers"]


@pytest.fixture
def data() -> Any:
    """Return a helper that unwraps the response envelope."""

    def unwrap(response: Any) -> Any:
        body = response.json()
        assert body["error"] is None, body["error"]
        return body["data"]

    return unwrap
