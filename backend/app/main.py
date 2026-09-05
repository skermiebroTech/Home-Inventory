"""The FastAPI application.

This module wires the routers, the error envelope, the static frontend, and
the startup migration.
"""

from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.config import settings
from app.database import dispose_engine
from app.routers import ALL_ROUTERS
from app.schemas.common import Envelope, ErrorDetail
from app.utils.errors import ApiError

logging.basicConfig(
    level=settings.log_level.upper(),
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
)
logger = logging.getLogger("homestock")

DESCRIPTION = """
A self-hosted home inventory system.

Every response uses the same envelope: `{"data": ..., "error": null}`.
On failure `data` is null and `error` holds a code and a message.

The server runs every AI model on the CPU. There is no GPU. The AI routes
return a job instead of a result when inference takes longer than
`HS_AI_INLINE_TIMEOUT` seconds.
"""


def _ensure_directories() -> None:
    """Create the data directories if they are missing."""
    for path in (
        settings.data_dir,
        settings.upload_dir,
        settings.backup_dir,
        settings.config_dir,
    ):
        try:
            path.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            logger.warning("Could not create %s: %s", path, exc)


def _run_migrations() -> None:
    """Run ``alembic upgrade head``.

    This is a blocking call. ``lifespan`` runs it in a worker thread.

    ``entrypoint.sh`` also runs the migration before uvicorn starts. This
    startup call covers the developer who runs uvicorn directly. Alembic
    takes a lock, so running it twice is safe.
    """
    from alembic import command
    from alembic.config import Config

    ini_path = Path(__file__).resolve().parent.parent / "alembic.ini"
    config = Config(str(ini_path))
    config.set_main_option("script_location", str(ini_path.parent / "alembic"))
    config.set_main_option("sqlalchemy.url", settings.database_url)
    command.upgrade(config, "head")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Prepare the service, then clean up when it stops."""
    os.environ.setdefault("TZ", settings.tz)
    _ensure_directories()

    if settings.secret_key_is_default:
        logger.warning(
            "HS_SECRET_KEY is still the default value. Change it before you "
            "expose this service."
        )

    if settings.run_migrations_on_start:
        try:
            await asyncio.to_thread(_run_migrations)
            logger.info("Database migrations are up to date.")
        except Exception as exc:
            # A failed migration must not stop the container. The health route
            # then reports the database as unmigrated, and the operator can
            # read the log and fix it.
            logger.error("Migration failed: %s", exc)

    logger.info("HomeStock %s is ready on port %s.", __version__, settings.port)
    yield
    await dispose_engine()


app = FastAPI(
    title="HomeStock",
    version=__version__,
    description=DESCRIPTION,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

# The service runs on a home network. The web interface, the mobile
# application, and any tablet on the LAN all call it from a different origin.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials="*" not in settings.cors_origin_list,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)


def _envelope_response(
    status_code: int, code: str, message: str, details: dict | None = None
) -> JSONResponse:
    """Return an error inside the standard envelope."""
    body = Envelope[None](
        data=None, error=ErrorDetail(code=code, message=message, details=details)
    )
    return JSONResponse(status_code=status_code, content=body.model_dump(mode="json"))


@app.exception_handler(ApiError)
async def handle_api_error(request: Request, exc: ApiError) -> JSONResponse:
    return _envelope_response(exc.status_code, exc.code, exc.message, exc.details)


@app.exception_handler(HTTPException)
async def handle_http_exception(
    request: Request, exc: HTTPException
) -> JSONResponse:
    return _envelope_response(
        exc.status_code, f"http_{exc.status_code}", str(exc.detail)
    )


@app.exception_handler(RequestValidationError)
async def handle_validation_error(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    return _envelope_response(
        status.HTTP_422_UNPROCESSABLE_ENTITY,
        "validation_error",
        "The request body or query is not valid.",
        {"errors": exc.errors()},
    )


@app.exception_handler(Exception)
async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return _envelope_response(
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        "internal_error",
        "The server failed to handle the request.",
    )


for router in ALL_ROUTERS:
    app.include_router(router)


# --- Uploaded media ---
#
# The file names hold UUIDs, so a path cannot be guessed. That is enough on a
# home network. If you publish this service on the internet, replace this
# mount with an authenticated route. Set HS_SERVE_MEDIA to false to turn the
# mount off.
if os.getenv("HS_SERVE_MEDIA", os.getenv("SERVE_MEDIA", "true")).lower() == "true":
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    app.mount(
        "/media",
        StaticFiles(directory=settings.upload_dir),
        name="media",
    )


# --- The built web interface ---
#
# The Docker image copies the Vite build into this directory. In development
# the directory is absent, and Vite serves the interface on its own port.
_index = settings.static_dir / "index.html"
if _index.is_file():
    # A placeholder build has no assets directory. Mounting a missing
    # directory raises at import time, so check first.
    _assets = settings.static_dir / "assets"
    if _assets.is_dir():
        app.mount("/assets", StaticFiles(directory=_assets), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str) -> FileResponse:
        """Return the single page application for any non-API path.

        The router in the browser owns these paths, so the server must return
        index.html instead of a 404.
        """
        candidate = (settings.static_dir / full_path).resolve()
        # Reject a path that climbs out of the static directory.
        if (
            full_path
            and candidate.is_file()
            and candidate.is_relative_to(settings.static_dir.resolve())
        ):
            return FileResponse(candidate)
        return FileResponse(_index)

else:
    logger.info(
        "No built frontend at %s. The API runs on its own.", settings.static_dir
    )
