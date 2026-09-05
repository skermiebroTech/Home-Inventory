"""Keep the phone models on the server.

A phone downloads about half a gigabyte, or nearly two, before it can name an
item on its own. Over a home line from a public host that can take an hour,
and every phone pays it again.

The server fetches each file once and serves it from the local network, where
the same download takes a minute. It also means the weights survive a phone
that is wiped, and a house with no internet still sets a new phone up.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

import httpx

from app.utils.settings import setting

logger = logging.getLogger(__name__)

#: Where the weights sit. The web server hands this directory out at /models.
CACHE_DIRNAME: Final[str] = "models"


@dataclass(frozen=True, slots=True)
class ModelFile:
    """One file of a model, and where it comes from."""

    part: str
    url: str
    bytes: int

    def name(self, model_id: str) -> str:
        """The file name on the server, which the phone asks for."""
        return f"{model_id}-{self.part}.gguf"


@dataclass(frozen=True, slots=True)
class CachedModel:
    """One model that a phone can run."""

    id: str
    name: str
    note: str
    files: tuple[ModelFile, ...]

    @property
    def bytes(self) -> int:
        return sum(one.bytes for one in self.files)


#: The models that the application offers. The phone holds the same list, so
#: that it still works when the server is away.
MODELS: Final[tuple[CachedModel, ...]] = (
    CachedModel(
        id="smolvlm2-2.2b",
        name="SmolVLM2 2.2B",
        note="Slower, and it names things better.",
        files=(
            ModelFile(
                part="model",
                url=(
                    "https://huggingface.co/ggml-org/SmolVLM2-2.2B-Instruct-GGUF"
                    "/resolve/main/SmolVLM2-2.2B-Instruct-Q4_K_M.gguf"
                ),
                bytes=1_112_602_656,
            ),
            ModelFile(
                part="mmproj",
                url=(
                    "https://huggingface.co/ggml-org/SmolVLM2-2.2B-Instruct-GGUF"
                    "/resolve/main/mmproj-SmolVLM2-2.2B-Instruct-Q8_0.gguf"
                ),
                bytes=592_523_200,
            ),
        ),
    ),
    CachedModel(
        id="smolvlm2-500m",
        name="SmolVLM2 500M",
        note="Quick, and it misses detail.",
        files=(
            ModelFile(
                part="model",
                url=(
                    "https://huggingface.co/ggml-org"
                    "/SmolVLM2-500M-Video-Instruct-GGUF/resolve/main"
                    "/SmolVLM2-500M-Video-Instruct-Q8_0.gguf"
                ),
                bytes=436_808_704,
            ),
            ModelFile(
                part="mmproj",
                url=(
                    "https://huggingface.co/ggml-org"
                    "/SmolVLM2-500M-Video-Instruct-GGUF/resolve/main"
                    "/mmproj-SmolVLM2-500M-Video-Instruct-Q8_0.gguf"
                ),
                bytes=108_785_184,
            ),
        ),
    ),
)


def model_by_id(model_id: str) -> CachedModel | None:
    return next((model for model in MODELS if model.id == model_id), None)


def cache_dir() -> Path:
    """Return the directory that holds the weights, and make it."""
    root = Path(str(setting("data_dir", "/data") or "/data")) / CACHE_DIRNAME
    root.mkdir(parents=True, exist_ok=True)
    return root


def path_of(model: CachedModel, one: ModelFile) -> Path:
    return cache_dir() / one.name(model.id)


def bytes_here(model: CachedModel) -> int:
    """How much of this model is already on the server."""
    total = 0
    for one in model.files:
        path = path_of(model, one)
        if path.exists():
            total += path.stat().st_size
    return total


def is_ready(model: CachedModel) -> bool:
    """True when every file is here and the whole size, not a part of it."""
    return all(
        path_of(model, one).exists() and path_of(model, one).stat().st_size >= one.bytes
        for one in model.files
    )


@dataclass
class FetchState:
    """What one running download is doing."""

    model_id: str
    written: int = 0
    total: int = 0
    error: str | None = None
    done: bool = False
    task: asyncio.Task[None] | None = field(default=None, repr=False)


#: The downloads that this process started, by model id.
_running: dict[str, FetchState] = {}


def state_of(model_id: str) -> FetchState | None:
    return _running.get(model_id)


async def _fetch_file(
    client: httpx.AsyncClient, url: str, target: Path, state: FetchState
) -> None:
    """Fetch one file, carrying on from a part that is already here."""
    have = target.stat().st_size if target.exists() else 0
    headers = {"Range": f"bytes={have}-"} if have else {}

    async with client.stream("GET", url, headers=headers, timeout=None) as response:
        if have and response.status_code == 200:
            # The host ignored the range, so start again.
            have = 0
            target.unlink(missing_ok=True)
        elif response.status_code not in (200, 206):
            response.raise_for_status()

        mode = "ab" if have else "wb"
        with target.open(mode) as handle:
            async for chunk in response.aiter_bytes(1024 * 512):
                handle.write(chunk)
                state.written += len(chunk)


async def _fetch(model: CachedModel, state: FetchState) -> None:
    """Fetch every file of one model."""
    state.total = model.bytes
    state.written = bytes_here(model)
    try:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            for one in model.files:
                target = path_of(model, one)
                if target.exists() and target.stat().st_size >= one.bytes:
                    continue
                logger.info("Fetching %s for the phones.", one.name(model.id))
                await _fetch_file(client, one.url, target, state)
        state.done = True
        logger.info("The model %s is on the server.", model.id)
    except Exception as exc:  # noqa: BLE001 - the state carries the reason
        state.error = str(exc)
        logger.warning("The fetch of %s stopped: %s", model.id, exc)


def start_fetch(model: CachedModel) -> FetchState:
    """Begin a download, or return the one that is already running."""
    running = _running.get(model.id)
    if running and not running.done and not running.error:
        return running

    state = FetchState(model_id=model.id, total=model.bytes, written=bytes_here(model))
    state.task = asyncio.create_task(_fetch(model, state))
    _running[model.id] = state
    return state


def forget(model: CachedModel) -> None:
    """Delete the files of one model from the server."""
    running = _running.pop(model.id, None)
    if running and running.task and not running.task.done():
        running.task.cancel()
    for one in model.files:
        path_of(model, one).unlink(missing_ok=True)
