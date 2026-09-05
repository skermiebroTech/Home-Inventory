"""The phone models that the server keeps.

The files themselves are handed out by the static mount at /models, which
answers a range request, so a phone that loses its connection carries on
where it stopped.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Path, status
from pydantic import BaseModel

from app.schemas.common import Envelope, Message, ok
from app.services.model_cache import (
    MODELS,
    bytes_here,
    forget,
    is_ready,
    model_by_id,
    start_fetch,
    state_of,
)
from app.utils.auth import CurrentUser
from app.utils.errors import not_found

router = APIRouter(prefix="/api/models", tags=["Phone models"])


class ModelFileRead(BaseModel):
    """One file of a model, and the two places it can come from."""

    part: str
    bytes: int
    #: The address on this server, which is fast and needs no internet.
    path: str
    #: Where the server fetched it, for a phone with no cached copy.
    origin: str


class ModelRead(BaseModel):
    """One model that a phone can run."""

    id: str
    name: str
    note: str
    bytes: int
    files: list[ModelFileRead]
    #: Every file is here, whole.
    ready: bool
    #: What is on the server now, part of a download included.
    cached_bytes: int
    fetching: bool = False
    error: str | None = None


def _read(model_id: str) -> ModelRead:
    model = model_by_id(model_id)
    if model is None:
        raise not_found("The model")

    running = state_of(model.id)
    return ModelRead(
        id=model.id,
        name=model.name,
        note=model.note,
        bytes=model.bytes,
        files=[
            ModelFileRead(
                part=one.part,
                bytes=one.bytes,
                path=f"/models/{one.name(model.id)}",
                origin=one.url,
            )
            for one in model.files
        ],
        ready=is_ready(model),
        cached_bytes=bytes_here(model),
        fetching=bool(running and not running.done and not running.error),
        error=running.error if running else None,
    )


@router.get(
    "",
    response_model=Envelope[list[ModelRead]],
    summary="List the models that a phone can run.",
    description=(
        "A model marked ready is on this server, and a phone downloads it "
        "over the local network instead of from the internet."
    ),
)
async def list_models(user: CurrentUser) -> Envelope[list[ModelRead]]:
    return ok([_read(model.id) for model in MODELS])


@router.post(
    "/{model_id}/fetch",
    response_model=Envelope[ModelRead],
    status_code=status.HTTP_202_ACCEPTED,
    summary="Fetch a model onto the server.",
    description=(
        "The work runs in the background. Ask this route again, or the list, "
        "to see how far it has come. A fetch that stopped carries on."
    ),
)
async def fetch_model(
    model_id: Annotated[str, Path(max_length=60)], user: CurrentUser
) -> Envelope[ModelRead]:
    model = model_by_id(model_id)
    if model is None:
        raise not_found("The model")
    start_fetch(model)
    return ok(_read(model.id))


@router.delete(
    "/{model_id}",
    response_model=Envelope[Message],
    summary="Delete a model from the server.",
)
async def delete_model(
    model_id: Annotated[str, Path(max_length=60)], user: CurrentUser
) -> Envelope[Message]:
    model = model_by_id(model_id)
    if model is None:
        raise not_found("The model")
    forget(model)
    return ok(Message(message="The model is off the server."))
