"""Unit tests for PDF/DOCX text extraction (app/ai_chat/attachments/extraction.py).

Fixtures are generated at test time (reportlab for PDF, python-docx for DOCX) --
no binary fixture files to keep in the repo. Every failure path (corrupted bytes,
encrypted PDF, wrong format) must degrade to None, never raise.
"""

import io

from app.ai_chat.attachments.extraction import extract_docx_text, extract_pdf_text


def _make_pdf(text: str) -> bytes:
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    c.drawString(100, 750, text)
    c.save()
    return buf.getvalue()


def _make_encrypted_pdf(text: str) -> bytes:
    from pypdf import PdfWriter

    plain = _make_pdf(text)
    reader_bytes = io.BytesIO(plain)
    from pypdf import PdfReader

    reader = PdfReader(reader_bytes)
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    writer.encrypt("secret")
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def _make_docx(paragraphs: list[str]) -> bytes:
    from docx import Document

    doc = Document()
    for p in paragraphs:
        doc.add_paragraph(p)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


# --- PDF ---------------------------------------------------------------------


def test_extract_pdf_text_returns_embedded_text():
    content = _make_pdf("Quarterly revenue grew 40 percent")
    text = extract_pdf_text(content)
    assert text is not None
    assert "revenue" in text.lower()


def test_extract_pdf_text_encrypted_returns_none():
    content = _make_encrypted_pdf("secret roadmap")
    assert extract_pdf_text(content) is None


def test_extract_pdf_text_corrupted_bytes_returns_none():
    assert extract_pdf_text(b"not a pdf at all") is None


def test_extract_pdf_text_empty_bytes_returns_none():
    assert extract_pdf_text(b"") is None


# --- DOCX ----------------------------------------------------------------------


def test_extract_docx_text_returns_paragraphs():
    content = _make_docx(["Founder update", "We closed our seed round."])
    text = extract_docx_text(content)
    assert text is not None
    assert "Founder update" in text
    assert "seed round" in text


def test_extract_docx_text_corrupted_bytes_returns_none():
    assert extract_docx_text(b"not a docx at all") is None


def test_extract_docx_text_empty_bytes_returns_none():
    assert extract_docx_text(b"") is None
