"""Reports APIs.

Ownership is enforced on every founder-scoped endpoint: a missing report is 404,
another founder's report is 403. The shared endpoint is PUBLIC and returns a
strict subset (headings + prose only) -- no facts, IDs, scores internals or
reasoning. internal_intelligence_reports is never reachable from here.
"""

from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_founder_record
from app.api.v1.reports.generator import ReportNarrative, ReportNarrativeGenerator
from app.api.v1.reports.gotenberg import GotenbergError, render_pdf
from app.api.v1.reports.payload import build_report_payload
from app.api.v1.reports.pdf import build_report_pdf
from app.api.v1.reports.print_html import build_report_html
from app.api.v1.reports.repository import reports_repository
from app.core.config import settings
from app.api.v1.reports.schemas import (
    InsightsView, ReportView, SectionOut, SectionSlice, ShareCreated,
    SharedReportView, SharedSection,
)
from app.db.session import get_db
from app.models import Founder, FounderReport

router = APIRouter(prefix="/reports", tags=["reports"])


# --- helpers ----------------------------------------------------------------
def _owned_report(db: Session, founder: Founder, report_id: int) -> FounderReport:
    report = db.get(FounderReport, report_id)
    if report is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Report not found.")
    if report.founder_id != founder.founder_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This report belongs to another founder.")
    return report


def _report_narrator(db: Session):
    """LLM section narrator when REPORT_NARRATIVE_LLM is on and a provider is
    available; otherwise None (the generator defaults to the template). Each
    section still degrades to the template + records it, so quality is never
    silently variable. Provider-build failure (no key/routing) => template."""
    from app.core.config import settings
    if not settings.REPORT_NARRATIVE_LLM:
        return None
    try:
        from app.api.v1.reports.narrator import LLMSectionNarrator
        from app.services.llm import LLMTask, provider_for_task
        from app.services.llm.text import make_sync_text
        provider = provider_for_task(db, LLMTask.REPORT_NARRATIVE)
        return LLMSectionNarrator(make_sync_text(provider, max_tokens=400))
    except Exception:  # no key / no routing -> template (recorded as 'template')
        from app.core.logger import logger
        logger.warning("report narrative LLM unavailable; using template narrator")
        return None


def _build_narrative(db: Session, report: FounderReport):
    """The report's narrative, generated once and cached forever after.

    A report's underlying facts are fixed at generation time -- nothing
    about session 54's answers changes because someone opened the report
    page twice. Every caller of this function used to trigger a fresh
    narrator run regardless, which with REPORT_NARRATIVE_LLM on meant the
    full LLM section narrator (7 sequential provider calls, ~27s
    live-measured) re-ran on every page view, DNA-tab switch, and PDF
    export of a report nobody had changed. Lazily cached on
    narrative_snapshot instead: first read generates and persists it,
    every read after that is a plain column fetch.

    Admin-triggered regeneration (panel_service.regenerate_report) clears
    narrative_snapshot on the new report row it creates, so a founder whose
    report is intentionally rebuilt still gets a fresh narrative once, not
    forever -- this cache is per report_id, not per founder.
    """
    if report.narrative_snapshot is not None:
        return ReportNarrative.from_dict(report.report_id, report.narrative_snapshot)

    payload = build_report_payload(db, report)
    framing = reports_repository.session_state_framing(db, report.session_state_at_generation)
    distress = None
    if report.distress_acknowledged_first or report.session_state_at_generation == "high_distress":
        distress = reports_repository.distress_protocol_text(db)
    narrative = ReportNarrativeGenerator(narrator=_report_narrator(db)).generate(
        payload, session_framing=framing, distress_protocol=distress,
    )

    report.narrative_snapshot = narrative.as_dict()
    db.commit()

    return narrative


def _section(narrative, key: str) -> SectionOut | None:
    for s in narrative.sections:
        if s.key == key:
            return SectionOut(key=s.key, heading=s.heading, prose=s.prose, facts=s.facts)
    return None


# --- founder-scoped endpoints ----------------------------------------------
@router.get("/shared/{token}", response_model=SharedReportView)
async def shared_report(token: str, db: Session = Depends(get_db)) -> SharedReportView:
    """PUBLIC. Strict subset: headings + prose only."""
    share = reports_repository.get_active_share(db, token)
    if share is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "This shared report is not available.")
    report = db.get(FounderReport, share.report_id)
    if report is None or not report.is_active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "This shared report is not available.")
    narrative = _build_narrative(db, report)
    return SharedReportView(
        variant=narrative.variant.value,
        sections=[SharedSection(heading=s.heading, prose=s.prose)
                  for s in narrative.sections if s.prose],
    )


@router.get("/{report_id}", response_model=ReportView)
async def full_report(
    report_id: int,
    founder: Founder = Depends(get_founder_record),
    db: Session = Depends(get_db),
) -> ReportView:
    report = _owned_report(db, founder, report_id)
    n = _build_narrative(db, report)
    return ReportView(
        report_id=report.report_id, variant=n.variant.value,
        tone_persona=n.tone_persona, generated_at=report.generated_at,
        exposes_numeric_scores=n.exposes_numeric_scores,
        sections=[SectionOut(key=s.key, heading=s.heading, prose=s.prose, facts=s.facts)
                  for s in n.sections],
        unpopulated_sections=list(n.unpopulated_sections),
        narrator_provenance=n.narrator_provenance,
    )


@router.get("/{report_id}/founder-dna", response_model=SectionSlice)
async def founder_dna(report_id: int, founder: Founder = Depends(get_founder_record),
                      db: Session = Depends(get_db)) -> SectionSlice:
    n = _build_narrative(db, _owned_report(db, founder, report_id))
    return SectionSlice(report_id=report_id, section=_section(n, "founder_dna"))


@router.get("/{report_id}/business-dna", response_model=SectionSlice)
async def business_dna(report_id: int, founder: Founder = Depends(get_founder_record),
                       db: Session = Depends(get_db)) -> SectionSlice:
    n = _build_narrative(db, _owned_report(db, founder, report_id))
    return SectionSlice(report_id=report_id, section=_section(n, "business_dna"))


@router.get("/{report_id}/insights", response_model=InsightsView)
async def insights(report_id: int, founder: Founder = Depends(get_founder_record),
                   db: Session = Depends(get_db)) -> InsightsView:
    n = _build_narrative(db, _owned_report(db, founder, report_id))
    return InsightsView(
        report_id=report_id, variant=n.variant.value,
        sections=[SectionOut(key=s.key, heading=s.heading, prose=s.prose, facts=s.facts)
                  for s in n.sections],
    )


@router.get("/{report_id}/recommendations", response_model=SectionSlice)
async def recommendations(report_id: int, founder: Founder = Depends(get_founder_record),
                          db: Session = Depends(get_db)) -> SectionSlice:
    n = _build_narrative(db, _owned_report(db, founder, report_id))
    return SectionSlice(report_id=report_id, section=_section(n, "priority_actions"))


@router.post("/{report_id}/export")
async def export_pdf(report_id: int, founder: Founder = Depends(get_founder_record),
                     db: Session = Depends(get_db)) -> Response:
    n = _build_narrative(db, _owned_report(db, founder, report_id))
    # Screen-parity path: print HTML -> Gotenberg. Fall back to reportlab if the
    # sidecar is unreachable, and FLAG which renderer produced the PDF so a
    # degraded (non-parity) export is never silent.
    try:
        pdf = render_pdf(build_report_html(n), base_url=settings.GOTENBERG_URL)
        renderer = "gotenberg"
    except GotenbergError:
        pdf = build_report_pdf(n)
        renderer = "reportlab-fallback"
    return Response(
        content=pdf, media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="clarity-report-{report_id}.pdf"',
            "X-PDF-Renderer": renderer,
        },
    )


@router.post("/{report_id}/share", response_model=ShareCreated, status_code=status.HTTP_201_CREATED)
async def share_report(
    report_id: int, request: Request,
    founder: Founder = Depends(get_founder_record),
    db: Session = Depends(get_db),
) -> ShareCreated:
    _owned_report(db, founder, report_id)  # ownership before creating a public link
    token = secrets.token_urlsafe(24)
    base = str(request.base_url).rstrip("/")
    share = reports_repository.create_share(
        db, founder_id=founder.founder_id, report_id=report_id, token=token, base_url=base,
    )
    return ShareCreated(
        share_token=share.share_token, share_url=share.share_url, expires_at=share.expires_at,
    )
