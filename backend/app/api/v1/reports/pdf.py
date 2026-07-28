"""Report PDF export.

No printable template exists in the frontend (no @media print / jsPDF / export
component), so the PDF mirrors the on-screen section ORDER -- the narrative
sections are already in that order -- rather than inventing a separate structure.
The export is the same document the founder saw, minus the unpopulated frontend
sections (evidence / roadmap / why-steps), which have no backend source.
"""

from __future__ import annotations

import io


def build_report_pdf(narrative) -> bytes:
    """Render a ReportNarrative to PDF bytes (reportlab)."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
    )
    from reportlab.lib import colors

    ss = getSampleStyleSheet()
    h = ParagraphStyle("h", parent=ss["Heading2"], fontSize=13, spaceBefore=10, spaceAfter=4)
    body = ParagraphStyle("b", parent=ss["Normal"], fontSize=10.5, leading=15)

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=20*mm, rightMargin=20*mm,
                            topMargin=18*mm, bottomMargin=18*mm, title="Founder Clarity Report")
    story = [Paragraph("Founder Clarity Report", ss["Title"]), Spacer(1, 8)]

    for s in narrative.sections:
        story.append(Paragraph(_esc(s.heading), h))
        if s.prose:
            story.append(Paragraph(_esc(s.prose), body))
        # Business DNA: render the pillar score cards as a small table.
        pillars = (s.facts or {}).get("pillars")
        if pillars:
            rows = [["Pillar", "Score", "Band"]]
            for p in pillars:
                rows.append([p.get("pillar_name", ""),
                             "-" if p.get("score") is None else str(p["score"]),
                             p.get("band") or "-"])
            t = Table(rows, colWidths=[70*mm, 25*mm, 55*mm])
            t.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f2e25")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#d5dae1")),
                ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]))
            story.append(Spacer(1, 4))
            story.append(t)
        story.append(Spacer(1, 6))

    doc.build(story)
    return buf.getvalue()


def _esc(t: str) -> str:
    return (t or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
