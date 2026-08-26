"""Turn uploaded bytes into model-viewable media blocks (images / PDF pages).

This is the path for files that TEXT extraction cannot reach: screenshots and
photos, which have no text layer at all, and scanned PDFs, whose pages are
images wearing a .pdf extension. `extraction.py` handles the files that DO have
extractable text, and it stays the preferred path -- a text PDF costs a few
hundred tokens as text and several thousand as pictures of itself, so this
module is a fallback for that case, never a replacement.

Everything here is deterministic given the same bytes and fails CLOSED: any
error returns None and the caller lists the file by name only, exactly as
before this module existed. A founder's turn never breaks because a file was
odd.

Cost is the reason for every cap below. A free founder has 4,000 chat tokens a
day (plans/catalog.py); an image costs roughly (width x height) / 750 of them,
so an unbounded upload could spend a whole day's allowance in one turn. Images
are downscaled to a pixel ceiling and PDFs truncated to a page ceiling so the
worst case per turn is bounded and predictable rather than whatever the
founder's camera happened to produce.
"""

from __future__ import annotations

import base64
import io

from app.ai_chat.attachments.schemas import SupportedMimeType
from app.api.v1.ally.execution.schemas import MediaBlock, MediaKind
from app.core.logger import logger

# Anthropic resizes anything above 1568px on an edge server-side, so going
# beyond it costs upload bandwidth and buys no detail. Sitting AT that ceiling
# rather than well under it is deliberate: the whole point of this module is
# reading a phone screenshot, and a 1080x2400 screenshot downscaled hard enough
# to be cheap is downscaled hard enough that its text stops being legible -- an
# image the model cannot read is worth less than the tokens it costs.
_MAX_IMAGE_EDGE = 1568
_MAX_IMAGE_PIXELS = 1_150_000          # ~1,530 tokens at (w*h)/750
_JPEG_QUALITY = 88

# Decompression-bomb guard: a small file can declare an enormous canvas.
_MAX_DECODED_PIXELS = 50_000_000

_MAX_PDF_VISION_PAGES = 5              # a 40-page scan is not a chat message
_MAX_MEDIA_BYTES = 5 * 1024 * 1024     # per block, matching the vendor image cap

_IMAGE_MIMES = frozenset({
    SupportedMimeType.PNG, SupportedMimeType.JPEG,
    SupportedMimeType.GIF, SupportedMimeType.WEBP,
})


def is_viewable(mime_type: SupportedMimeType) -> bool:
    """Whether this file has a media path at all. DOCX does not: it is text or
    nothing, and a DOCX that fails text extraction is corrupt rather than
    scanned."""
    return mime_type in _IMAGE_MIMES or mime_type is SupportedMimeType.PDF


def build_media(
    content: bytes,
    mime_type: SupportedMimeType,
    filename: str,
    *,
    max_pdf_pages: int = _MAX_PDF_VISION_PAGES,
) -> MediaBlock | None:
    if mime_type in _IMAGE_MIMES:
        return _image_block(content, mime_type, filename)
    if mime_type is SupportedMimeType.PDF:
        return _pdf_block(content, filename, max_pages=max_pdf_pages)
    return None


# --- images ---------------------------------------------------------------


def _image_block(content: bytes, mime_type: SupportedMimeType, filename: str) -> MediaBlock | None:
    try:
        from PIL import Image

        Image.MAX_IMAGE_PIXELS = _MAX_DECODED_PIXELS
        with Image.open(io.BytesIO(content)) as img:
            img.load()
            if _within_budget(img.width, img.height) and len(content) <= _MAX_MEDIA_BYTES:
                # Already small enough. Re-encoding here would only lose detail
                # and, for a PNG screenshot, introduce the JPEG artefacts that
                # small text suffers most from.
                return MediaBlock(MediaKind.IMAGE, mime_type.value,
                                  base64.b64encode(content).decode("ascii"), filename)
            data, out_mime = _downscale(img)
        if data is None:
            return None
        return MediaBlock(MediaKind.IMAGE, out_mime,
                          base64.b64encode(data).decode("ascii"), filename)
    except Exception as exc:  # noqa: BLE001 -- fail closed, never raise
        logger.warning("attachments: image media build failed",
                       extra={"stage": "build_image_media", "error": str(exc)})
        return None


def _within_budget(width: int, height: int) -> bool:
    return (
        width * height <= _MAX_IMAGE_PIXELS
        and max(width, height) <= _MAX_IMAGE_EDGE
    )


def _downscale(img):
    """Shrink to the pixel/edge ceiling, preserving aspect ratio.

    Encoded as JPEG unless the image has real transparency, because a phone
    screenshot as PNG runs several megabytes and carries no benefit the model
    can use. Transparency is flattened onto white rather than dropped -- an
    alpha channel discarded outright turns transparent pixels black, which on a
    screenshot with a transparent background hides exactly the text being
    asked about.
    """
    from PIL import Image

    width, height = img.size
    if width <= 0 or height <= 0:
        return None, ""

    scale = min(
        1.0,
        (_MAX_IMAGE_PIXELS / (width * height)) ** 0.5,
        _MAX_IMAGE_EDGE / max(width, height),
    )
    target = (max(1, int(width * scale)), max(1, int(height * scale)))

    has_alpha = img.mode in ("RGBA", "LA") or "transparency" in img.info
    resized = img.convert("RGBA" if has_alpha else "RGB").resize(target, Image.LANCZOS)
    if has_alpha:
        flat = Image.new("RGB", target, (255, 255, 255))
        flat.paste(resized, mask=resized.split()[-1])
        resized = flat

    buf = io.BytesIO()
    resized.save(buf, format="JPEG", quality=_JPEG_QUALITY, optimize=True)
    data = buf.getvalue()
    if len(data) > _MAX_MEDIA_BYTES:
        return None, ""
    return data, SupportedMimeType.JPEG.value


# --- documents ------------------------------------------------------------


def _pdf_block(content: bytes, filename: str, *, max_pages: int) -> MediaBlock | None:
    try:
        from pypdf import PdfReader, PdfWriter

        reader = PdfReader(io.BytesIO(content))
        if reader.is_encrypted:
            return None
        total = len(reader.pages)
        if total == 0:
            return None
        if total <= max_pages and len(content) <= _MAX_MEDIA_BYTES:
            return MediaBlock(MediaKind.DOCUMENT, SupportedMimeType.PDF.value,
                              base64.b64encode(content).decode("ascii"), filename,
                              pages_sent=total, pages_total=total)

        writer = PdfWriter()
        for page in reader.pages[:max_pages]:
            writer.add_page(page)
        buf = io.BytesIO()
        writer.write(buf)
        data = buf.getvalue()
        if len(data) > _MAX_MEDIA_BYTES:
            return None
        return MediaBlock(MediaKind.DOCUMENT, SupportedMimeType.PDF.value,
                          base64.b64encode(data).decode("ascii"), filename,
                          pages_sent=min(max_pages, total), pages_total=total)
    except Exception as exc:  # noqa: BLE001 -- fail closed, never raise
        logger.warning("attachments: PDF media build failed",
                       extra={"stage": "build_pdf_media", "error": str(exc)})
        return None
