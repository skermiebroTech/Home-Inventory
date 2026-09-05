"""Image storage: EXIF GPS removal, resize, and thumbnail generation.

Every uploaded image goes through `store_image`. It writes one resized
original and one file for each configured thumbnail width into
`{HS_UPLOAD_DIR}/{items|receipts|locations}/{id}/`.
"""

from __future__ import annotations

import shutil
import uuid
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Final, Literal

import anyio.to_thread
from PIL import Image, ImageOps, UnidentifiedImageError

from app.utils.settings import setting

UploadKind = Literal["items", "receipts", "locations"]

#: The EXIF tag that holds the GPS pointer.
GPS_IFD_TAG: Final[int] = 0x8825

DEFAULT_MAX_DIMENSION: Final[int] = 2000
DEFAULT_THUMBNAIL_WIDTHS: Final[tuple[int, ...]] = (200, 600)
JPEG_QUALITY: Final[int] = 88

#: Pillow formats that this application accepts.
ALLOWED_FORMATS: Final[frozenset[str]] = frozenset(
    {"JPEG", "PNG", "WEBP", "HEIF", "HEIC", "GIF", "BMP", "TIFF"}
)


class UnsupportedImageError(ValueError):
    """The uploaded bytes are not an image that this application accepts."""


@dataclass(frozen=True, slots=True)
class StoredImage:
    """The result of one image upload."""

    original_path: Path
    thumbnails: dict[int, Path]
    width: int
    height: int
    content_type: str
    byte_size: int
    gps_removed: bool = False

    @property
    def relative_original(self) -> str:
        """Return the original path, relative to the upload directory."""
        return to_relative(self.original_path)

    @property
    def relative_thumbnails(self) -> dict[int, str]:
        """Return the thumbnail paths, relative to the upload directory."""
        return {w: to_relative(p) for w, p in self.thumbnails.items()}

    @property
    def primary_thumbnail(self) -> Path | None:
        """Return the smallest thumbnail, which the list views use."""
        if not self.thumbnails:
            return None
        return self.thumbnails[min(self.thumbnails)]


@dataclass(frozen=True, slots=True)
class ImageOptions:
    """The tunable parts of the image pipeline."""

    max_dimension: int = DEFAULT_MAX_DIMENSION
    thumbnail_widths: tuple[int, ...] = DEFAULT_THUMBNAIL_WIDTHS
    strip_gps: bool = True
    quality: int = JPEG_QUALITY

    @classmethod
    def from_settings(cls) -> ImageOptions:
        """Build the options from the application settings."""
        return cls(
            max_dimension=int(setting("image_max_dimension", DEFAULT_MAX_DIMENSION)),
            thumbnail_widths=parse_widths(
                setting("thumbnail_sizes", DEFAULT_THUMBNAIL_WIDTHS)
            ),
            strip_gps=bool(setting("strip_exif_gps", True)),
        )


def parse_widths(value: object) -> tuple[int, ...]:
    """Read thumbnail widths from a list, a tuple, or a comma separated string."""
    if isinstance(value, str):
        parts = [p.strip() for p in value.split(",") if p.strip()]
    elif isinstance(value, list | tuple):
        parts = [str(p).strip() for p in value]
    else:
        return DEFAULT_THUMBNAIL_WIDTHS
    widths = sorted({int(p) for p in parts if p.isdigit() and int(p) > 0})
    return tuple(widths) or DEFAULT_THUMBNAIL_WIDTHS


# --------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------


def upload_root() -> Path:
    """Return the root directory for all uploads."""
    return Path(str(setting("upload_dir", "/data/uploads")))


def upload_dir_for(kind: UploadKind, entity_id: uuid.UUID | str) -> Path:
    """Return `{HS_UPLOAD_DIR}/{kind}/{id}/` and create it."""
    directory = upload_root() / kind / str(entity_id)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def to_relative(path: Path | str) -> str:
    """Return a path relative to the upload root, for storage in the database."""
    candidate = Path(path)
    root = upload_root()
    try:
        return str(candidate.relative_to(root))
    except ValueError:
        return str(candidate)


def to_absolute(relative_path: str) -> Path:
    """Return the absolute path of a stored relative path."""
    candidate = Path(relative_path)
    if candidate.is_absolute():
        return candidate
    return upload_root() / candidate


# --------------------------------------------------------------------------
# Storage
# --------------------------------------------------------------------------


async def store_image(
    data: bytes,
    *,
    kind: UploadKind,
    entity_id: uuid.UUID | str,
    options: ImageOptions | None = None,
) -> StoredImage:
    """Store one uploaded image and its thumbnails.

    The work is CPU bound, so it runs in a worker thread.
    """
    opts = options or ImageOptions.from_settings()
    directory = upload_dir_for(kind, entity_id)
    return await anyio.to_thread.run_sync(
        lambda: store_image_sync(data, directory=directory, options=opts)
    )


def store_image_sync(
    data: bytes,
    *,
    directory: Path,
    options: ImageOptions | None = None,
    stem: str | None = None,
) -> StoredImage:
    """Store one image. This call blocks; `store_image` wraps it in a thread."""
    opts = options or ImageOptions.from_settings()
    directory.mkdir(parents=True, exist_ok=True)
    name = stem or uuid.uuid4().hex

    with _open_image(data) as source:
        image = ImageOps.exif_transpose(source) or source
        exif_bytes, gps_removed = _exif_without_gps(image, strip=opts.strip_gps)
        use_png = _has_alpha(image)
        suffix = ".png" if use_png else ".jpg"

        original = _fit(image, opts.max_dimension)
        original_path = directory / f"{name}{suffix}"
        _save(
            original,
            original_path,
            use_png=use_png,
            exif=exif_bytes,
            quality=opts.quality,
        )

        thumbnails: dict[int, Path] = {}
        for width in opts.thumbnail_widths:
            thumb = _resize_to_width(original, width)
            thumb_path = directory / f"{name}_{width}{suffix}"
            _save(thumb, thumb_path, use_png=use_png, exif=None, quality=opts.quality)
            thumbnails[width] = thumb_path

        return StoredImage(
            original_path=original_path,
            thumbnails=thumbnails,
            width=original.width,
            height=original.height,
            content_type="image/png" if use_png else "image/jpeg",
            byte_size=original_path.stat().st_size,
            gps_removed=gps_removed,
        )


def delete_stored_image(
    original_path: Path | str, thumbnails: dict[int, Path | str] | None = None
) -> None:
    """Delete one original and its thumbnails. Missing files are ignored."""
    paths: list[Path] = [to_absolute(str(original_path))]
    for thumb in (thumbnails or {}).values():
        paths.append(to_absolute(str(thumb)))
    for path in paths:
        path.unlink(missing_ok=True)


def thumbnail_path_for(original_path: Path | str, width: int) -> Path | None:
    """Return the generated thumbnail of one width, if the file is there.

    The insurance report uses it to place a readable photograph without
    loading the full sized original.
    """
    original = to_absolute(str(original_path))
    candidate = original.with_name(f"{original.stem}_{width}{original.suffix}")
    return candidate if candidate.is_file() else None


def delete_image_set(original_path: Path | str) -> None:
    """Delete one stored original and every thumbnail generated from it.

    The thumbnails sit beside the original and carry the same stem plus the
    pixel width, so one glob finds them all.
    """
    original = to_absolute(str(original_path))
    directory = original.parent
    stem = original.stem
    original.unlink(missing_ok=True)
    if not directory.is_dir():
        return
    for sibling in directory.glob(f"{stem}_*"):
        if sibling.is_file():
            sibling.unlink(missing_ok=True)


def delete_entity_dir(kind: UploadKind, entity_id: uuid.UUID | str) -> None:
    """Delete every file that belongs to one item, receipt, or location."""
    shutil.rmtree(upload_root() / kind / str(entity_id), ignore_errors=True)


# --------------------------------------------------------------------------
# Pillow helpers
# --------------------------------------------------------------------------


def _open_image(data: bytes) -> Image.Image:
    """Open the uploaded bytes, or raise `UnsupportedImageError`."""
    if not data:
        raise UnsupportedImageError("The uploaded file is empty.")
    try:
        image = Image.open(BytesIO(data))
        image.load()
    except UnidentifiedImageError as exc:
        raise UnsupportedImageError("The file is not an image.") from exc
    except (OSError, ValueError) as exc:
        raise UnsupportedImageError(f"The image is damaged: {exc}") from exc
    if image.format and image.format.upper() not in ALLOWED_FORMATS:
        raise UnsupportedImageError(f"The format {image.format} is not accepted.")
    return image


def _exif_without_gps(image: Image.Image, *, strip: bool) -> tuple[bytes | None, bool]:
    """Return the EXIF block with the GPS pointer removed."""
    try:
        exif = image.getexif()
    except Exception:  # noqa: BLE001 - an unreadable EXIF block is dropped
        return None, False
    if not exif:
        return None, False
    had_gps = GPS_IFD_TAG in exif
    if strip and had_gps:
        del exif[GPS_IFD_TAG]
    try:
        return exif.tobytes(), (had_gps and strip)
    except Exception:  # noqa: BLE001 - an EXIF block that will not re-encode is dropped
        # An EXIF block that Pillow cannot re-encode is dropped, which is safe.
        return None, had_gps


def _has_alpha(image: Image.Image) -> bool:
    """Return True if the image carries transparency."""
    return image.mode in ("RGBA", "LA", "PA") or "transparency" in image.info


def _fit(image: Image.Image, max_dimension: int) -> Image.Image:
    """Return a copy that fits inside a `max_dimension` square."""
    result = image.copy()
    if max(result.width, result.height) > max_dimension:
        result.thumbnail((max_dimension, max_dimension), Image.LANCZOS)
    return result


def _resize_to_width(image: Image.Image, width: int) -> Image.Image:
    """Return a copy at the given width. The image is never made larger."""
    target = min(width, image.width)
    height = max(1, round(image.height * target / image.width))
    return image.resize((target, height), Image.LANCZOS)


def _save(
    image: Image.Image,
    path: Path,
    *,
    use_png: bool,
    exif: bytes | None,
    quality: int,
) -> None:
    """Write one image to disk in PNG or JPEG format."""
    if use_png:
        image.save(path, format="PNG", optimize=True)
        return
    flat = image
    if flat.mode not in ("RGB", "L"):
        flat = flat.convert("RGB")
    kwargs: dict[str, object] = {
        "format": "JPEG",
        "quality": quality,
        "optimize": True,
        "progressive": True,
    }
    if exif:
        kwargs["exif"] = exif
    flat.save(path, **kwargs)


#: Kept so that callers can list the widths without building options.
DEFAULT_OPTIONS: Final[ImageOptions] = ImageOptions()

__all__ = [
    "DEFAULT_OPTIONS",
    "ImageOptions",
    "StoredImage",
    "UnsupportedImageError",
    "UploadKind",
    "delete_entity_dir",
    "delete_image_set",
    "delete_stored_image",
    "parse_widths",
    "store_image",
    "store_image_sync",
    "thumbnail_path_for",
    "to_absolute",
    "to_relative",
    "upload_dir_for",
    "upload_root",
]
