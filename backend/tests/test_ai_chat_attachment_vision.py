"""Attachments the model looks at rather than reads about.

Before this path existed, every image and every scanned PDF reached the prompt
as one line -- "uploaded, but its contents cannot be read yet; you only know it
exists" -- and Ally, correctly, told the founder it could not see the file. A
founder who uploads a screenshot and asks "what does this say" got an apology.

These tests pin the whole chain end to end: bytes -> MediaBlock -> context
window -> ProviderRequest -> the Anthropic wire payload, plus the caps that keep
one upload from spending a founder's whole daily token allowance, and the
fail-closed behaviour that means a strange file degrades to naming instead of
breaking the turn.
"""

import base64
import io
from types import SimpleNamespace

import pytest
from PIL import Image

from app.ai_chat.attachments.media import build_media, is_viewable
from app.ai_chat.attachments.schemas import AttachmentType, SupportedMimeType
from app.api.v1.ally.execution.schemas import MediaBlock, MediaKind, ProviderRequest
from app.api.v1.ally.prompts.grounding.flatteners import attachments_block
from app.integrations.llm.adapters import ClaudeAdapter, DEFAULT_OPTIONS, OpenAIAdapter

PDF, PNG, JPEG = SupportedMimeType.PDF, SupportedMimeType.PNG, SupportedMimeType.JPEG


# --- fixtures --------------------------------------------------------------


def png_bytes(width=400, height=300, mode="RGB", colour=(30, 90, 60)):
    buf = io.BytesIO()
    Image.new(mode, (width, height), colour).save(buf, format="PNG")
    return buf.getvalue()


def text_pdf(lines=("Runway is eleven months",)):
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    for i, line in enumerate(lines):
        c.drawString(72, 750 - 20 * i, line)
    c.save()
    return buf.getvalue()


def scanned_pdf(pages=1):
    """A PDF whose pages are pictures -- no text layer, exactly what a phone
    scan or a university calendar export produces."""
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas

    img = ImageReader(io.BytesIO(png_bytes(600, 800)))
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    for _ in range(pages):
        c.drawImage(img, 0, 0, width=400, height=600)
        c.showPage()
    c.save()
    return buf.getvalue()


def decoded(block):
    return base64.b64decode(block.data_base64)


# --- what has a media path at all -----------------------------------------


@pytest.mark.parametrize("mime", [PNG, JPEG, SupportedMimeType.GIF, SupportedMimeType.WEBP, PDF])
def test_images_and_pdfs_are_viewable(mime):
    assert is_viewable(mime) is True


def test_docx_has_no_media_path():
    """A DOCX that fails text extraction is corrupt, not scanned -- rendering it
    as pictures would be paying vision prices for a broken file."""
    assert is_viewable(SupportedMimeType.DOCX) is False
    assert build_media(b"PK\x03\x04 not really", SupportedMimeType.DOCX, "notes.docx") is None


# --- images ---------------------------------------------------------------


def test_screenshot_becomes_an_image_block():
    block = build_media(png_bytes(), PNG, "Screenshot.png")
    assert block.kind is MediaKind.IMAGE
    assert block.filename == "Screenshot.png"
    assert decoded(block) == png_bytes()          # small enough to pass through


def test_small_image_is_not_re_encoded():
    """Re-encoding a small PNG screenshot as JPEG would add exactly the
    artefacts that small text suffers from, for no saving worth having."""
    block = build_media(png_bytes(), PNG, "s.png")
    assert block.mime_type == PNG.value


def test_phone_screenshot_is_downscaled_within_the_token_ceiling():
    tall = png_bytes(1080, 2400)
    block = build_media(tall, PNG, "Screenshot_2026-08-25.png")
    img = Image.open(io.BytesIO(decoded(block)))
    assert max(img.size) <= 1568
    assert img.size[0] * img.size[1] <= 1_150_000
    # ~(w*h)/750 tokens -- bounded well under a free founder's 4,000/day.
    assert (img.size[0] * img.size[1]) / 750 < 2_000
    assert len(decoded(block)) < len(tall)


def test_downscaling_preserves_aspect_ratio():
    block = build_media(png_bytes(2000, 1000), PNG, "wide.png")
    w, h = Image.open(io.BytesIO(decoded(block))).size
    assert abs((w / h) - 2.0) < 0.01


def test_transparency_is_flattened_onto_white_not_dropped():
    """Dropping an alpha channel turns transparent pixels black. On a screenshot
    with a transparent background that hides the very text being asked about."""
    buf = io.BytesIO()
    Image.new("RGBA", (2000, 2000), (0, 0, 0, 0)).save(buf, format="PNG")
    block = build_media(buf.getvalue(), PNG, "transparent.png")
    img = Image.open(io.BytesIO(decoded(block))).convert("RGB")
    assert img.getpixel((img.width // 2, img.height // 2)) == (255, 255, 255)


def test_corrupt_image_fails_closed():
    assert build_media(b"this is not an image", PNG, "broken.png") is None


# --- documents ------------------------------------------------------------


def test_scanned_pdf_becomes_a_document_block():
    block = build_media(scanned_pdf(), PDF, "Academic Calendar.pdf")
    assert block.kind is MediaKind.DOCUMENT
    assert block.mime_type == PDF.value
    assert block.truncated is False


def test_long_scan_is_truncated_and_says_so():
    block = build_media(scanned_pdf(pages=12), PDF, "big-scan.pdf", max_pdf_pages=5)
    assert (block.pages_sent, block.pages_total) == (5, 12)
    assert block.truncated is True

    from pypdf import PdfReader
    assert len(PdfReader(io.BytesIO(decoded(block))).pages) == 5


def test_truncation_is_stated_in_the_prompt():
    """A model handed 5 pages of 40 with no note answers as though it saw all
    40 -- the founder asks about page 12 and gets a confident answer from page
    3."""
    block = build_media(scanned_pdf(pages=12), PDF, "big-scan.pdf", max_pdf_pages=5)
    text = attachments_block(((("big-scan.pdf"), "document", 900_000, None, block),))
    assert "first 5 of 12 pages" in text


def test_whole_document_carries_no_truncation_note():
    block = build_media(scanned_pdf(pages=2), PDF, "short.pdf", max_pdf_pages=5)
    text = attachments_block((("short.pdf", "document", 9000, None, block),))
    assert "pages were attached" not in text


def test_corrupt_pdf_fails_closed():
    assert build_media(b"%PDF-1.4 truncated garbage", PDF, "broken.pdf") is None


# --- the prompt's account of what was sent --------------------------------


def test_a_file_sent_as_media_is_not_described_as_unreadable():
    """The bug this whole path exists to fix. The block is the model's only
    account of what it was given: leave the old wording in place and it
    apologises for not seeing a picture it is looking at."""
    block = MediaBlock(MediaKind.IMAGE, "image/png", "AAAA", "Screenshot.png")
    text = attachments_block((("Screenshot.png", "image", 412_000, None, block),))
    assert "cannot read its contents" not in text
    assert "you only know it exists" not in text
    assert "look at" in text


def test_a_file_with_neither_text_nor_media_is_still_named_only():
    text = attachments_block((("mystery.docx", "document", 4096, None, None),))
    assert "cannot read its contents" in text


def test_extracted_text_still_wins_over_everything():
    text = attachments_block((("notes.txt", "text", 64, "runway is 11 months", None),))
    assert "runway is 11 months" in text
    assert "look at" not in text


def test_legacy_four_field_entries_still_format():
    """attachments_block is called with 4-tuples by anything built before media
    existed; widening the row must not break those callers."""
    text = attachments_block((("old.txt", "text", 12, "hello"),))
    assert "hello" in text


# --- the wire payload -----------------------------------------------------


def _request(media=()):
    from decimal import Decimal
    return ProviderRequest(system="sys", user="what does this say?", model="claude-sonnet-5",
                           temperature=Decimal("0"), max_tokens=1024, media=tuple(media))


def test_text_only_turn_sends_a_plain_string_exactly_as_before():
    """Nearly every turn has no attachment. None of them should be reshaped by
    a feature they do not use."""
    payload = ClaudeAdapter().build_payload(_request(), "claude-sonnet-5", DEFAULT_OPTIONS)
    assert payload["messages"] == [{"role": "user", "content": "what does this say?"}]


def test_image_is_sent_as_an_image_block_ahead_of_the_prompt():
    block = build_media(png_bytes(), PNG, "s.png")
    payload = ClaudeAdapter().build_payload(_request([block]), "claude-sonnet-5", DEFAULT_OPTIONS)
    content = payload["messages"][0]["content"]
    assert [c["type"] for c in content] == ["image", "text"]
    assert content[0]["source"] == {
        "type": "base64", "media_type": "image/png", "data": block.data_base64,
    }
    assert content[-1]["text"] == "what does this say?"


def test_pdf_is_sent_as_a_document_block():
    block = build_media(scanned_pdf(), PDF, "scan.pdf")
    payload = ClaudeAdapter().build_payload(_request([block]), "claude-sonnet-5", DEFAULT_OPTIONS)
    content = payload["messages"][0]["content"]
    assert [c["type"] for c in content] == ["document", "text"]
    assert content[0]["source"]["media_type"] == "application/pdf"


def test_provider_without_media_support_still_sends_the_question():
    """Degrading to text is acceptable; losing the founder's message is not."""
    block = build_media(png_bytes(), PNG, "s.png")
    payload = OpenAIAdapter().build_payload(_request([block]), "gpt-4o-mini", DEFAULT_OPTIONS)
    assert payload["messages"][-1]["content"] == "what does this say?"


# --- context window: which files get media, and how many ------------------


class FakeAttachment:
    def __init__(self, attachment_id, filename, attachment_type, size_bytes, mime_type):
        self.attachment_id = attachment_id
        self.metadata = SimpleNamespace(
            filename=filename, attachment_type=attachment_type,
            size_bytes=size_bytes, mime_type=mime_type,
        )


class FakeAttachments:
    def __init__(self, items=(), content=None):
        self._items, self._content = items, content or {}

    def list_attachments(self, conversation_id):
        return self._items

    def get_content(self, attachment_id):
        return self._content.get(attachment_id)


def _window(items, content, **config):
    from tests.test_ai_chat_context_window import _conv_with, make_ctx, setup
    from app.ai_chat import ContextWindowConfig

    conv, builder = setup(attachments=FakeAttachments(items=items, content=content),
                          config=ContextWindowConfig(**config) if config else None)
    c = _conv_with(conv, ("user", "what does this say?"))
    return builder.build(ally_context=make_ctx(), conversation=c,
                         current_message="what does this say?")


def _img(n="shot.png", aid="a1", data=None):
    data = data if data is not None else png_bytes()
    return FakeAttachment(aid, n, AttachmentType.IMAGE, len(data), PNG), data


def test_image_upload_produces_media_on_the_window():
    """The builder still works. It is the TRANSPORT that cannot carry an
    image, which is why _DEFAULT_MEDIA_LIMIT is 0 -- so this asks for the
    limit explicitly rather than relying on a default that is off."""
    att, data = _img()
    w = _window((att,), {"a1": data}, media_limit=2)
    assert len(w.media) == 1
    assert w.media[0].kind is MediaKind.IMAGE
    assert "cannot read its contents" not in w.attachments_text


def test_text_pdf_is_read_as_text_not_paid_for_as_pictures():
    """A born-digital PDF costs a few hundred tokens as text and several
    thousand as pictures of the same words."""
    data = text_pdf()
    att = FakeAttachment("a2", "board.pdf", AttachmentType.DOCUMENT, len(data), PDF)
    w = _window((att,), {"a2": data})
    assert w.media == ()
    assert "Runway is eleven months" in w.attachments_text


def test_scanned_pdf_falls_through_to_vision():
    data = scanned_pdf()
    att = FakeAttachment("a3", "calendar.pdf", AttachmentType.DOCUMENT, len(data), PDF)
    w = _window((att,), {"a3": data}, media_limit=2)
    assert len(w.media) == 1
    assert w.media[0].kind is MediaKind.DOCUMENT


def test_media_is_capped_per_turn():
    items, content = [], {}
    for i in range(5):
        att, data = _img(n=f"s{i}.png", aid=f"a{i}")
        items.append(att)
        content[f"a{i}"] = data
    w = _window(tuple(items), content, media_limit=2)
    assert len(w.media) == 2                       # the cap asked for above


def test_the_cap_keeps_the_newest_files():
    """When more files qualify than there are slots, the one just uploaded is
    the one being asked about."""
    items, content = [], {}
    for i in range(4):
        att, data = _img(n=f"s{i}.png", aid=f"a{i}")
        items.append(att)
        content[f"a{i}"] = data
    w = _window(tuple(items), content, media_limit=2)
    assert {b.filename for b in w.media} == {"s2.png", "s3.png"}


def test_media_limit_zero_restores_the_old_naming_only_behaviour():
    att, data = _img()
    w = _window((att,), {"a1": data}, media_limit=0)
    assert w.media == ()
    assert "cannot read its contents" in w.attachments_text


def test_unreadable_file_never_breaks_the_turn():
    att = FakeAttachment("a9", "broken.png", AttachmentType.IMAGE, 12, PNG)
    w = _window((att,), {"a9": b"not an image"})
    assert w.media == ()
    assert w.attachments_injected is True
    assert "broken.png" in w.attachments_text


# --- cost of deciding ------------------------------------------------------


class CountingAttachments(FakeAttachments):
    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.reads = 0

    def get_content(self, attachment_id):
        self.reads += 1
        return super().get_content(attachment_id)


def test_a_pdf_is_read_once_per_turn_not_once_per_question_asked_of_it():
    """Choosing between text and vision means asking whether text extraction
    finds anything, and the prompt block then wants that same text. Done
    naively that parses a 200-page PDF twice and fetches its bytes three times,
    on every turn the file stays attached."""
    from tests.test_ai_chat_context_window import _conv_with, make_ctx, setup

    data = text_pdf()
    att = FakeAttachment("p1", "board.pdf", AttachmentType.DOCUMENT, len(data), PDF)
    store = CountingAttachments(items=(att,), content={"p1": data})
    conv, builder = setup(attachments=store)
    c = _conv_with(conv, ("user", "what is our runway?"))
    w = builder.build(ally_context=make_ctx(), conversation=c, current_message="what is our runway?")

    assert store.reads == 1
    assert "Runway is eleven months" in w.attachments_text


def test_the_memo_does_not_survive_between_turns():
    """A file replaced between turns must not be answered from a stale read."""
    from tests.test_ai_chat_context_window import _conv_with, make_ctx, setup

    first, second = text_pdf(("Runway is eleven months",)), text_pdf(("Runway is four months",))
    att = FakeAttachment("p2", "board.pdf", AttachmentType.DOCUMENT, len(first), PDF)
    store = FakeAttachments(items=(att,), content={"p2": first})
    conv, builder = setup(attachments=store)
    c = _conv_with(conv, ("user", "runway?"))

    builder.build(ally_context=make_ctx(), conversation=c, current_message="runway?")
    store._content["p2"] = second
    w = builder.build(ally_context=make_ctx(), conversation=c, current_message="and now?")

    assert "four months" in w.attachments_text
    assert "eleven months" not in w.attachments_text
