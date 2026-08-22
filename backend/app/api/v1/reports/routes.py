"""Reports APIs.

Ownership is enforced on every founder-scoped endpoint: a missing report is 404,
another founder's report is 403. The shared endpoint is PUBLIC and returns a
strict subset (headings + prose only) -- no facts, IDs, scores internals or
reasoning. internal_intelligence_reports is never reachable from here.
"""

from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.api.deps import get_founder_record
from app.api.v1.reports.document import build_report_document
from app.api.v1.reports.generator import ReportNarrative, ReportNarrativeGenerator
from app.api.v1.reports.payload import build_report_payload
from app.api.v1.reports.pdf_delivery import (
    mark_pdf_requested,
    render_and_store,
    stored_pdf,
)
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


def share_url_for(token: str, request: Request) -> str:
    """The public URL for a share token.

    `/r/<token>` is a REWRITE on the Vercel frontend (see frontend/vercel.json),
    not a route on this backend -- so it only resolves against the site's own
    origin. Building it against the API host instead produces a link that 404s,
    which is the worst possible outcome for a feature whose entire job is to
    hand someone a working URL.

    So the pretty path is used only when PUBLIC_APP_URL says where the site
    lives. Without it we fall back to this API's own endpoint, which is uglier
    but always resolves. A link that works beats a link that looks right.
    """
    site = (settings.PUBLIC_APP_URL or "").strip().rstrip("/")
    if site:
        return f"{site}/r/{token}"
    base = str(request.base_url).rstrip("/")
    return f"{base}/api/v1/reports/shared/{token}/view"


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


@router.get("/shared/{token}/view", response_class=HTMLResponse)
async def shared_report_page(token: str, db: Session = Depends(get_db)) -> HTMLResponse:
    """PUBLIC. The shared report as a readable page.

    The share link used to point at the JSON endpoint above, so whoever a founder
    sent it to opened a wall of JSON. This renders the same document the founder
    sees, through the same builder.

    It is the FULL report, by product decision (2026-08-21): a link that shows a
    stripped-down version is not the thing the founder thought they were sharing.
    That means a visitor sees the wellbeing note and the founder's own answers,
    so two guards matter here and are not optional:

      * `noindex, nofollow` -- an unlisted link is not a secret one, and a search
        engine that crawls it would make a founder's psychological state a public
        search result. This is the difference between "anyone I send it to" and
        "anyone at all".
      * No Download or Share controls (`with_actions=False`): both call endpoints
        that require the founder's own session, so to a visitor they are buttons
        that can only fail.

    Access control, expiry and the access counter all live in get_active_share.
    An expired, revoked or unknown token is a 404 -- deliberately the same answer
    for all three, so the endpoint cannot be used to probe which tokens exist.
    """
    share = reports_repository.get_active_share(db, token)
    if share is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "This shared report is not available.")
    report = db.get(FounderReport, share.report_id)
    if report is None or not report.is_active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "This shared report is not available.")

    founder = db.get(Founder, report.founder_id)
    return HTMLResponse(
        build_report_document(
            _build_narrative(db, report),
            report.insights,
            founder_name=getattr(founder, "full_name", None),
            generated_at=report.generated_at,
            with_actions=False,
        ),
        headers={
            "X-Robots-Tag": "noindex, nofollow, noarchive",
            # Shares are revocable and expire; a cached copy in a CDN would
            # outlive the revocation the founder just performed.
            "Cache-Control": "private, no-store",
        },
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


@router.get("/{report_id}/document", response_class=HTMLResponse)
async def report_document(
    report_id: int,
    founder: Founder = Depends(get_founder_record),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """The report as a rendered HTML document -- the same one the PDF is made of.

    The screen and the PDF are the same builder with one flag between them
    (app/api/v1/reports/document.py), so "the download looks like the page" is a
    property of the code rather than something two implementations have to keep
    agreeing on. The React page mounts this in an isolated frame; Gotenberg
    renders the print variant of the identical markup.

    Not cached at the HTTP layer: the narrative behind it already is
    (narrative_snapshot), so a repeat view is a column fetch plus string
    assembly, and a stale document is worse than a cheap one.
    """
    report = _owned_report(db, founder, report_id)
    narrative = _build_narrative(db, report)
    return HTMLResponse(build_report_document(
        narrative,
        report.insights,
        founder_name=founder.full_name,
        generated_at=report.generated_at,
    ))


@router.post("/{report_id}/export")
async def export_pdf(report_id: int, founder: Founder = Depends(get_founder_record),
                     db: Session = Depends(get_db)) -> Response:
    """The founder's report as a PDF -- or an honest "not yet", never a substitute.

    This used to fall back to a plain reportlab document whenever Gotenberg was
    unreachable. Both paths return 200 with a real application/pdf body, so a
    founder who downloaded during a blip got the wrong document and nothing ever
    tried again. A missing PDF is recoverable; a wrong one that looks fine is
    not, and it is the founder who carries the cost.

    Order: serve the stored copy, else render and keep it, else say so and put
    the request in the backfill sweep's queue.
    """
    report = _owned_report(db, founder, report_id)

    pdf = stored_pdf(report)
    if pdf is None:
        pdf = render_and_store(db, report, _build_narrative(db, report))

    if pdf is None:
        mark_pdf_requested(db, report)
        # 503 + Retry-After, not 500: nothing is broken about this founder's
        # report, the renderer is momentarily unavailable and the backfill sweep
        # is now holding their place. The message is written for the founder,
        # because this one is shown to them rather than logged.
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Your report PDF is still being prepared. It'll be ready in a few "
            "minutes — try the download again shortly. Nothing is lost; your "
            "report is on screen in the meantime.",
            headers={"Retry-After": "300"},
        )

    return Response(
        content=pdf, media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="clarity-report-{report_id}.pdf"',
            # Kept: it is now always "gotenberg", so anything else in a log means
            # this endpoint grew a second renderer again.
            "X-PDF-Renderer": "gotenberg",
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
    share = reports_repository.create_share(
        db, founder_id=founder.founder_id, report_id=report_id, token=token,
        share_url=share_url_for(token, request),
    )
    return ShareCreated(
        share_token=share.share_token, share_url=share.share_url, expires_at=share.expires_at,
    )
