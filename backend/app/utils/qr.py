"""QR code generation for item and location labels."""

from __future__ import annotations

import uuid
from io import BytesIO
from typing import Final, Literal

import anyio.to_thread
import qrcode
from PIL import Image, ImageDraw, ImageFont
from qrcode.constants import ERROR_CORRECT_M

from app.utils.settings import setting

LabelKind = Literal["item", "location"]

DEFAULT_BOX_SIZE: Final[int] = 8
DEFAULT_BORDER: Final[int] = 2
CAPTION_FONT_SIZE: Final[int] = 16
CAPTION_PADDING: Final[int] = 8


def qr_payload(
    kind: LabelKind, entity_id: uuid.UUID | str, base_url: str | None = None
) -> str:
    """Return the text that one label encodes.

    The text is a deep link, so a normal phone camera opens the record in the
    web interface. The mobile application reads the same link and routes to its
    own screen.
    """
    root = (base_url or str(setting("public_url", "") or "")).rstrip("/")
    path = f"/{kind}s/{entity_id}"
    return f"{root}{path}" if root else f"homestock:{kind}:{entity_id}"


def generate_qr_png(
    data: str,
    *,
    box_size: int = DEFAULT_BOX_SIZE,
    border: int = DEFAULT_BORDER,
    caption: str | None = None,
    width: int | None = None,
) -> bytes:
    """Return one QR code as PNG bytes, with an optional caption below it.

    This call blocks. Use `render_qr_png` in a route handler.
    """
    if not data:
        raise ValueError("The QR code needs data to encode.")

    code = qrcode.QRCode(
        version=None,
        error_correction=ERROR_CORRECT_M,
        box_size=max(1, box_size),
        border=max(0, border),
    )
    code.add_data(data)
    code.make(fit=True)
    image = code.make_image(fill_color="black", back_color="white").convert("RGB")

    if width:
        # NEAREST keeps the module edges hard, so a printed label scans well.
        scale = width / image.width
        image = image.resize(
            (width, max(1, round(image.height * scale))), Image.NEAREST
        )

    if caption:
        image = _add_caption(image, caption)

    buffer = BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


async def render_qr_png(
    data: str,
    *,
    box_size: int = DEFAULT_BOX_SIZE,
    border: int = DEFAULT_BORDER,
    caption: str | None = None,
) -> bytes:
    """Render a QR code in a worker thread, so the event loop stays free."""
    return await anyio.to_thread.run_sync(
        lambda: generate_qr_png(data, box_size=box_size, border=border, caption=caption)
    )


async def render_label_png(
    kind: LabelKind,
    entity_id: uuid.UUID | str,
    *,
    caption: str | None = None,
    base_url: str | None = None,
    box_size: int = DEFAULT_BOX_SIZE,
    width: int | None = None,
) -> bytes:
    """Render the printable label of one item or one location."""
    return await render_qr_png(
        qr_payload(kind, entity_id, base_url),
        box_size=box_size,
        caption=caption,
        width=width,
    )


def _add_caption(image: Image.Image, caption: str) -> Image.Image:
    """Return a new image with `caption` centred under the QR code."""
    font = _caption_font()
    text = caption.strip()
    draw = ImageDraw.Draw(image)
    left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
    text_width = right - left
    text_height = bottom - top

    if text_width > image.width:
        text = _shorten(draw, text, font, image.width)
        left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
        text_width = right - left
        text_height = bottom - top

    height = image.height + text_height + CAPTION_PADDING * 2
    canvas = Image.new("RGB", (image.width, height), "white")
    canvas.paste(image, (0, 0))
    writer = ImageDraw.Draw(canvas)
    writer.text(
        ((image.width - text_width) / 2, image.height + CAPTION_PADDING - top),
        text,
        font=font,
        fill="black",
    )
    return canvas


def _shorten(
    draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, width: int
) -> str:
    """Cut a caption that is wider than the QR code and add an ellipsis."""
    ellipsis = "..."
    shortened = text
    while shortened and draw.textlength(shortened + ellipsis, font=font) > width:
        shortened = shortened[:-1]
    return (shortened + ellipsis) if shortened else text[:1]


def _caption_font() -> ImageFont.ImageFont:
    """Return the caption font. Pillow always supplies a default."""
    try:
        return ImageFont.load_default(size=CAPTION_FONT_SIZE)
    except TypeError:
        # Pillow older than 10.1 has no size argument.
        return ImageFont.load_default()


__all__ = [
    "LabelKind",
    "generate_qr_png",
    "qr_payload",
    "render_label_png",
    "render_qr_png",
]
