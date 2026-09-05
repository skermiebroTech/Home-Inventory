"""Errors, and the helper that every stub route calls."""

from __future__ import annotations

from typing import Any, NoReturn

from fastapi import HTTPException, status


class ApiError(HTTPException):
    """An error that carries a stable code for the client to branch on."""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(status_code=status_code, detail=message)
        self.code = code
        self.message = message
        self.details = details


def not_found(what: str) -> ApiError:
    """Return a 404 error for a missing row."""
    return ApiError(status.HTTP_404_NOT_FOUND, "not_found", f"{what} was not found.")


def forbidden(message: str = "You may not do that.") -> ApiError:
    """Return a 403 error."""
    return ApiError(status.HTTP_403_FORBIDDEN, "forbidden", message)


def unauthorized(message: str = "Sign in first.") -> ApiError:
    """Return a 401 error."""
    return ApiError(status.HTTP_401_UNAUTHORIZED, "unauthorized", message)


def conflict(message: str) -> ApiError:
    """Return a 409 error."""
    return ApiError(status.HTTP_409_CONFLICT, "conflict", message)


def unavailable(code: str, message: str) -> ApiError:
    """Return a 503 error, for a dependency that is down."""
    return ApiError(status.HTTP_503_SERVICE_UNAVAILABLE, code, message)


def not_implemented(route: str) -> NoReturn:
    """Raise a 501 error.

    Every stub route calls this. Phase 2 replaces the call with real logic.
    """
    raise ApiError(
        status.HTTP_501_NOT_IMPLEMENTED,
        "not_implemented",
        f"{route} is not implemented yet.",
    )
