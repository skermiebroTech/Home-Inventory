"""Authentication helpers and the current user dependency.

This module holds the password and token primitives, and the dependency that
turns a bearer token into a `User` row. `app/config.py` supplies the signing
key, the algorithm, and the two lifetimes.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any, Final

import anyio.to_thread
import bcrypt
import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_session
from app.models.user import User
from app.utils.errors import forbidden, unauthorized

bearer_scheme = HTTPBearer(auto_error=False, description="A JWT access token.")

SessionDep = Annotated[AsyncSession, Depends(get_session)]
BearerDep = Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)]

TOKEN_TYPE_ACCESS: Final[str] = "access"
TOKEN_TYPE_REFRESH: Final[str] = "refresh"

#: bcrypt reads a maximum of 72 bytes. A longer password is a caller error.
MAX_PASSWORD_BYTES: Final[int] = 72
BCRYPT_ROUNDS: Final[int] = 12


class TokenError(Exception):
    """The token is malformed, expired, or of the wrong type."""


@dataclass(frozen=True, slots=True)
class TokenPayload:
    """The claims that this application puts in every token."""

    subject: str
    token_type: str
    jti: str
    issued_at: datetime
    expires_at: datetime
    claims: dict[str, Any]

    @property
    def user_id(self) -> uuid.UUID:
        """Return the subject as a UUID."""
        return uuid.UUID(self.subject)


# --------------------------------------------------------------------------
# Passwords
# --------------------------------------------------------------------------


def hash_password(password: str) -> str:
    """Hash a password with bcrypt.

    This call is CPU bound. A route handler uses `hash_password_async`.
    """
    return bcrypt.hashpw(
        _password_bytes(password), bcrypt.gensalt(rounds=BCRYPT_ROUNDS)
    ).decode("ascii")


def verify_password(password: str, password_hash: str) -> bool:
    """Check a password against a bcrypt hash."""
    try:
        raw = _password_bytes(password)
    except ValueError:
        return False
    try:
        return bcrypt.checkpw(raw, password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        # The stored value is not a bcrypt hash.
        return False


async def hash_password_async(password: str) -> str:
    """Hash a password in a worker thread, so the event loop stays free."""
    return await anyio.to_thread.run_sync(hash_password, password)


async def verify_password_async(password: str, password_hash: str) -> bool:
    """Check a password in a worker thread, so the event loop stays free."""
    return await anyio.to_thread.run_sync(verify_password, password, password_hash)


def _password_bytes(password: str) -> bytes:
    """Return the UTF-8 bytes of a password, or raise if it is too long."""
    raw = password.encode("utf-8")
    if len(raw) > MAX_PASSWORD_BYTES:
        raise ValueError(f"The password must be {MAX_PASSWORD_BYTES} bytes or less.")
    return raw


# --------------------------------------------------------------------------
# Tokens
# --------------------------------------------------------------------------


def create_access_token(user_id: str | uuid.UUID) -> str:
    """Make a short lived JWT access token."""
    return _encode(
        user_id,
        TOKEN_TYPE_ACCESS,
        timedelta(minutes=settings.access_token_expire_minutes),
    )


def create_refresh_token(user_id: str | uuid.UUID) -> str:
    """Make a long lived JWT refresh token."""
    return _encode(
        user_id,
        TOKEN_TYPE_REFRESH,
        timedelta(days=settings.refresh_token_expire_days),
    )


def access_token_lifetime_seconds() -> int:
    """Return the access token lifetime in seconds."""
    return settings.access_token_expire_minutes * 60


def _encode(user_id: str | uuid.UUID, token_type: str, lifetime: timedelta) -> str:
    """Build and sign one token."""
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "typ": token_type,
        "jti": uuid.uuid4().hex,
        "iat": int(now.timestamp()),
        "exp": int((now + lifetime).timestamp()),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str, *, expected_type: str | None = None) -> TokenPayload:
    """Decode and verify a token.

    Raise `TokenError` if the signature is wrong, the token is expired, or the
    type does not agree with `expected_type`.
    """
    try:
        claims: dict[str, Any] = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.jwt_algorithm],
            options={"require": ["exp", "iat", "sub"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise TokenError("The token is expired.") from exc
    except jwt.InvalidTokenError as exc:
        raise TokenError("The token is not valid.") from exc

    token_type = str(claims.get("typ", ""))
    if expected_type is not None and token_type != expected_type:
        raise TokenError(f"This route needs a {expected_type} token.")

    subject = str(claims.get("sub", ""))
    try:
        uuid.UUID(subject)
    except ValueError as exc:
        raise TokenError("The token subject is not a user id.") from exc

    return TokenPayload(
        subject=subject,
        token_type=token_type,
        jti=str(claims.get("jti", "")),
        issued_at=datetime.fromtimestamp(int(claims["iat"]), tz=UTC),
        expires_at=datetime.fromtimestamp(int(claims["exp"]), tz=UTC),
        claims=claims,
    )


# --------------------------------------------------------------------------
# Dependencies
# --------------------------------------------------------------------------


async def get_current_user(
    credentials: BearerDep,
    session: SessionDep,
) -> User:
    """Return the signed in user, or raise 401."""
    if credentials is None or not credentials.credentials:
        raise unauthorized("This route needs a bearer token.")
    try:
        payload = decode_token(credentials.credentials, expected_type=TOKEN_TYPE_ACCESS)
    except TokenError as exc:
        raise unauthorized(str(exc)) from exc

    user = await session.get(User, payload.user_id)
    if user is None:
        raise unauthorized("The account of this token no longer exists.")
    if not user.is_active:
        raise unauthorized("This account is turned off.")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_admin(user: User) -> None:
    """Raise 403 unless the user owns the installation.

    The first account that registers becomes the admin. Only that role may
    run a restore, because a restore replaces every row and every file.
    """
    if user.role != "admin":
        raise forbidden("Only an administrator may do that.")


__all__ = [
    "TOKEN_TYPE_ACCESS",
    "TOKEN_TYPE_REFRESH",
    "BearerDep",
    "CurrentUser",
    "SessionDep",
    "TokenError",
    "TokenPayload",
    "access_token_lifetime_seconds",
    "bearer_scheme",
    "create_access_token",
    "create_refresh_token",
    "decode_token",
    "get_current_user",
    "hash_password",
    "hash_password_async",
    "require_admin",
    "verify_password",
    "verify_password_async",
]
