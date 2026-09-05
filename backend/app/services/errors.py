"""Error types that the service layer raises.

The router layer catches `ServiceError` and turns it into the standard
envelope: `{"data": null, "error": {"code": ..., "message": ...}}`.
"""

from __future__ import annotations

from typing import Any


class ServiceError(Exception):
    """The base class of every failure that a service reports."""

    code: str = "service_error"
    status_code: int = 500

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def to_payload(self) -> dict[str, Any]:
        """Return the body of the `error` key of the response envelope."""
        payload: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.details:
            payload["details"] = self.details
        return payload


class NotFoundError(ServiceError):
    """The requested record does not exist."""

    code = "not_found"
    status_code = 404


class ValidationError(ServiceError):
    """The request data is not acceptable."""

    code = "validation_error"
    status_code = 422


class ConflictError(ServiceError):
    """The request conflicts with the stored state."""

    code = "conflict"
    status_code = 409


class UpstreamError(ServiceError):
    """An external service answered with an error."""

    code = "upstream_error"
    status_code = 502


class ServiceUnavailableError(ServiceError):
    """A dependency of this feature is not available."""

    code = "service_unavailable"
    status_code = 503


class AIUnavailableError(ServiceUnavailableError):
    """Ollama is disabled, unreachable, or too slow."""

    code = "ai_unavailable"


class OCRUnavailableError(ServiceUnavailableError):
    """Tesseract is not installed in the container."""

    code = "ocr_unavailable"


class BackupError(ServiceError):
    """A backup or an export failed."""

    code = "backup_failed"


def to_api_error(exc: ServiceError) -> Any:
    """Turn a service failure into the HTTP error that the routers raise.

    The import is local, so that the service layer does not depend on FastAPI
    at import time.
    """
    from app.utils.errors import ApiError

    return ApiError(exc.status_code, exc.code, exc.message, exc.details or None)


__all__ = [
    "AIUnavailableError",
    "BackupError",
    "ConflictError",
    "NotFoundError",
    "OCRUnavailableError",
    "ServiceError",
    "ServiceUnavailableError",
    "UpstreamError",
    "ValidationError",
    "to_api_error",
]
