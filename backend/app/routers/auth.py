"""Authentication routes."""

from __future__ import annotations

from fastapi import APIRouter, status
from sqlalchemy import func, select

from app.models.user import User
from app.schemas.auth import LoginRequest, RefreshRequest, RegisterRequest, TokenPair
from app.schemas.common import Envelope, ok
from app.schemas.user import UserRead
from app.utils.auth import (
    TOKEN_TYPE_REFRESH,
    CurrentUser,
    SessionDep,
    TokenError,
    access_token_lifetime_seconds,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password_async,
    verify_password_async,
)
from app.utils.errors import conflict, unauthorized

router = APIRouter(prefix="/api/auth", tags=["Auth"])

#: A valid bcrypt hash of a value that no password matches. Comparing against
#: it keeps the reply time of a wrong email close to the reply time of a wrong
#: password, so the endpoint does not reveal which accounts exist.
_DUMMY_HASH = "$2b$12$C6UzMDM.H6dfI/f/IKcEeO3q7Z0VmM0G0zVQ.qc9O9pQ4dQe2nq0K"


def _tokens_for(user: User) -> TokenPair:
    """Build a fresh token pair for a user."""
    return TokenPair(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
        expires_in=access_token_lifetime_seconds(),
    )


async def _find_by_email(session: SessionDep, email: str) -> User | None:
    """Find one account by email, without regard to letter case."""
    statement = select(User).where(func.lower(User.email) == email.strip().lower())
    return (await session.execute(statement)).scalars().first()


@router.post(
    "/register",
    response_model=Envelope[UserRead],
    status_code=status.HTTP_201_CREATED,
    summary="Create the first user, or add another user.",
)
async def register(body: RegisterRequest, session: SessionDep) -> Envelope[UserRead]:
    email = body.email.strip().lower()
    if await _find_by_email(session, email) is not None:
        raise conflict("An account with that email address already exists.")

    # The first account owns the installation, so it becomes the admin.
    existing = await session.scalar(select(func.count()).select_from(User))
    role = "admin" if not existing else "user"

    user = User(
        email=email,
        name=body.name.strip(),
        password_hash=await hash_password_async(body.password),
        role=role,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return ok(UserRead.model_validate(user))


@router.post("/login", response_model=Envelope[TokenPair], summary="Sign in.")
async def login(body: LoginRequest, session: SessionDep) -> Envelope[TokenPair]:
    user = await _find_by_email(session, body.email)
    password_hash = user.password_hash if user else _DUMMY_HASH
    correct = await verify_password_async(body.password, password_hash)

    if user is None or not correct:
        raise unauthorized("The email address or the password is wrong.")
    if not user.is_active:
        raise unauthorized("This account is turned off.")
    return ok(_tokens_for(user))


@router.post(
    "/refresh",
    response_model=Envelope[TokenPair],
    summary="Trade a refresh token for a new token pair.",
)
async def refresh(body: RefreshRequest, session: SessionDep) -> Envelope[TokenPair]:
    try:
        payload = decode_token(body.refresh_token, expected_type=TOKEN_TYPE_REFRESH)
    except TokenError as exc:
        raise unauthorized(str(exc)) from exc

    user = await session.get(User, payload.user_id)
    if user is None:
        raise unauthorized("The account of this token no longer exists.")
    if not user.is_active:
        raise unauthorized("This account is turned off.")
    return ok(_tokens_for(user))


@router.get(
    "/me", response_model=Envelope[UserRead], summary="Return the signed in user."
)
async def me(user: CurrentUser) -> Envelope[UserRead]:
    return ok(UserRead.model_validate(user))
