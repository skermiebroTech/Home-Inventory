"""The rate limit on the sign in routes.

Every other route needs a token, so an unknown caller can only reach these
two. A limit here stops a password guessing run from a single address.

Set ``HS_RATE_LIMIT_AUTH`` to an empty string to turn the limit off. The test
suite does that, because it signs in many times in one second.
"""

from __future__ import annotations

from fastapi import status
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.config import settings

#: The shared limiter. `main.py` puts it on the application state.
limiter = Limiter(key_func=get_remote_address, enabled=bool(settings.rate_limit_auth))


def auth_limit() -> str:
    """Return the limit that the sign in routes use.

    The routes pass this function itself to slowapi, not its result, so the
    value is read on every request. A change to the setting then applies with
    no restart, and the test suite can raise or lower it.
    """
    return settings.rate_limit_auth or "1000/minute"


def rate_limit_handler(exc: RateLimitExceeded) -> JSONResponse:
    """Answer a refused request with the standard envelope."""
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={
            "data": None,
            "error": {
                "code": "rate_limited",
                "message": (
                    "Too many attempts from this address. "
                    f"The limit is {exc.detail}."
                ),
                "details": None,
            },
        },
    )


__all__ = ["auth_limit", "limiter", "rate_limit_handler"]
