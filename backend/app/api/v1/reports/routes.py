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
from app.api.v1.entitlement_gates import require_reports
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
    InsightsView, ReportView, SectionOut, SectionSlice, ShareCreated, ShareOut,
    SharedReportView, SharedSection,
)
from app.core.logger import logger
from app.db.session import get_db, set_admin_rls_context
from app.models import Founder, FounderReport


#: The public answer for every share failure, whatever the real cause.
_SHARE_UNAVAILABLE = "This shared report is not available."


def _resolve_share_or_404(db: Session, token: str, *, route: str):
    """Resolve a share token, or raise the one public 404 both share routes use.

    The visitor-facing answer is deliberately identical for an unknown token, a
    revoked or expired share, and a share whose report has been deactivated --
    otherwise the endpoint tells a stranger which tokens exist.

    That is right for the response and useless for us. A founder reporting "my
    share link says it is not available" could mean any of three different
    faults, and from the outside they are indistinguishable, so the first step
    of every investigation is a guess. The reason is logged here instead: same
    404 to the visitor, a named cause in our logs. The token itself is never
    logged -- it is the credential.
    """
    # THE SHARE ROUTES ARE SYSTEM ACTORS AND MUST SAY SO TO THE DATABASE.
    #
    # This is the one read in the product with no founder identity by design:
    # a share link is opened by an investor, a co-founder, a stranger -- nobody
    # who is signed in. So `get_founder_record` is deliberately not a dependency
    # here, and therefore `set_founder_rls_context` never runs.
    #
    # But `report_shares` and `founder_reports` are both founder-scoped under
    # row-level security (migration d91c6e4b72aa), whose policy is
    # `founder_id = get_founder_id() OR app.current_admin`. With neither set,
    # get_founder_id() is NULL, the comparison is NULL, and the policy hides
    # EVERY row -- so the lookup below found nothing and every share link on
    # earth answered "This shared report is not available." The row was always
    # there. This connection simply could not see it.
    #
    # Not observable in local development, which connects as a BYPASSRLS
    # superuser and never exercises the policy. Only production runs as
    # `ally_app`, which is why this was reproducible for founders and not here.
    #
    # THE TOKEN IS THE ACCESS CONTROL, and it always was: a 32-character random
    # value, looked up exactly, returning one share and its one report. Nothing
    # here accepts a founder_id, lists anything, or widens with user input --
    # so admin context grants this request no reach beyond the row whose token
    # the visitor already holds. Same reasoning, and the same call, as the
    # Razorpay webhook, which is the other genuine system actor in the app.
    # Transaction-local, so it dies with this request.
    set_admin_rls_context(db)

    share = reports_repository.get_active_share(db, token)
    if share is None:
        # Covers all three of unknown / revoked / expired: get_active_share
        # returns None for each, and looking further to tell them apart would
        # mean a second query on every probe.
        logger.warning("share_link_rejected", extra={
            "reason": "token_unknown_revoked_or_expired", "route": route,
            "token_len": len(token),
        })
        raise HTTPException(status.HTTP_404_NOT_FOUND, _SHARE_UNAVAILABLE)

    report = db.get(FounderReport, share.report_id)
    if report is None or not report.is_active:
        # A live share pointing at a report that has gone. The founder sees the
        # same sentence as a bad token, but this one is our fault, not theirs.
        logger.warning("share_link_rejected", extra={
            "reason": "report_missing" if report is None else "report_inactive",
            "route": route, "share_id": share.share_id, "report_id": share.report_id,
        })
        raise HTTPException(status.HTTP_404_NOT_FOUND, _SHARE_UNAVAILABLE)

    return share, report

# Gated on Feature.REPORTS at the router, so an endpoint added later is
# protected by default rather than by its author remembering -- the same
# reasoning as require_vision. The two share-token endpoints CANNOT live here:
# they are read by whoever the founder sent a link to, who has no founder row
# and no plan, so they sit on public_router below.
router = APIRouter(prefix="/reports", tags=["reports"],
                   dependencies=[Depends(require_reports)])

# PUBLIC. No auth, no entitlement -- a share token is the credential. Included
# BEFORE the gated router in api/v1/router.py so `/reports/shared/{token}`
# keeps the route precedence it has today.
public_router = APIRouter(prefix="/reports", tags=["reports"])


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
    """The public URL for a share token. It must resolve, above all else.

    THIS USED TO BUILD `<PUBLIC_APP_URL>/r/<token>` AND THAT BROKE EVERY SHARE
    LINK -- not because the path was wrong, but because PUBLIC_APP_URL points at
    the MARKETING SITE (goxlally.ai) rather than the app (app.goxlally.ai).

    `/r/:token` is a rewrite declared in frontend/vercel.json, and it works --
    verified against production: app.goxlally.ai/r/<anything> returns this API's
    own "This shared report is not available." So the rewrite was never the
    problem. The host was. Links went to goxlally.ai/r/<token>, which redirects
    to www and lands on the marketing site's 404 page, and the founder sees a
    dead link for a feature whose entire job is handing someone a working URL.

    PUBLIC_APP_URL is deliberately NOT consulted here any more. It has its own
    job -- bouncing a founder back to /app/plan after the calendar OAuth dance --
    and quietly borrowing it for a second purpose is how one wrong value broke
    two unrelated features at once. (It broke that one too: the calendar callback
    returns founders to goxlally.ai/app/plan, which also 404s.)

    THE DEFAULT IS THE DIRECT API URL, which needs no rewrite, no second domain
    and no configuration. Longer than /r/<token>, and it resolves wherever this
    service is reachable.

    SET SHARE_LINK_BASE_URL=https://app.goxlally.ai IN PRODUCTION to get the
    pretty path back, since that rewrite genuinely exists there. It is opt-in
    rather than inferred because the failure mode is silent: a base URL whose
    rewrite is missing produces links that look perfect and 404, and nothing in
    this codebase can detect that.

    The path is reversed out of the route table rather than written as a literal,
    so it follows the router if this module is ever remounted under a different
    prefix. A hardcoded "/api/v1/..." would keep looking correct while pointing
    at nothing.
    """
    path = request.app.url_path_for("shared_report_page", token=token)

    pretty = (settings.SHARE_LINK_BASE_URL or "").strip().rstrip("/")
    if pretty:
        return f"{pretty}/r/{token}"

    base = (settings.PUBLIC_API_URL or "").strip().rstrip("/")
    if base:
        return f"{base}{path}"
    # Last resort: the origin this very request arrived on. Correct whenever the
    # API is reached directly, and wrong only behind a proxy that rewrites Host
    # without forwarding it -- which is exactly what PUBLIC_API_URL is for.
    return f"{str(request.base_url).rstrip('/')}{path}"


# --- public share-token endpoints -------------------------------------------
# Mislabelled "founder-scoped" until the entitlement gate went in: both of these
# take a token and no founder, which is exactly why they must stay ungated.
@public_router.get("/shared/{token}", response_model=SharedReportView)
def shared_report(token: str, db: Session = Depends(get_db)) -> SharedReportView:
    """PUBLIC. Strict subset: headings + prose only."""
    _share, report = _resolve_share_or_404(db, token, route="json")
    narrative = _build_narrative(db, report)
    return SharedReportView(
        variant=narrative.variant.value,
        sections=[SharedSection(heading=s.heading, prose=s.prose)
                  for s in narrative.sections if s.prose],
    )


@public_router.get("/shared/{token}/view", response_class=HTMLResponse)
def shared_report_page(token: str, db: Session = Depends(get_db)) -> HTMLResponse:
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
    _share, report = _resolve_share_or_404(db, token, route="view")

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
def full_report(
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
def founder_dna(report_id: int, founder: Founder = Depends(get_founder_record),
                      db: Session = Depends(get_db)) -> SectionSlice:
    n = _build_narrative(db, _owned_report(db, founder, report_id))
    return SectionSlice(report_id=report_id, section=_section(n, "founder_dna"))


@router.get("/{report_id}/business-dna", response_model=SectionSlice)
def business_dna(report_id: int, founder: Founder = Depends(get_founder_record),
                       db: Session = Depends(get_db)) -> SectionSlice:
    n = _build_narrative(db, _owned_report(db, founder, report_id))
    return SectionSlice(report_id=report_id, section=_section(n, "business_dna"))


@router.get("/{report_id}/insights", response_model=InsightsView)
def insights(report_id: int, founder: Founder = Depends(get_founder_record),
                   db: Session = Depends(get_db)) -> InsightsView:
    n = _build_narrative(db, _owned_report(db, founder, report_id))
    return InsightsView(
        report_id=report_id, variant=n.variant.value,
        sections=[SectionOut(key=s.key, heading=s.heading, prose=s.prose, facts=s.facts)
                  for s in n.sections],
    )


@router.get("/{report_id}/recommendations", response_model=SectionSlice)
def recommendations(report_id: int, founder: Founder = Depends(get_founder_record),
                          db: Session = Depends(get_db)) -> SectionSlice:
    n = _build_narrative(db, _owned_report(db, founder, report_id))
    return SectionSlice(report_id=report_id, section=_section(n, "priority_actions"))


@router.get("/{report_id}/document", response_class=HTMLResponse)
def report_document(
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
def export_pdf(report_id: int, founder: Founder = Depends(get_founder_record),
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
def share_report(
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


@router.get("/{report_id}/shares", response_model=list[ShareOut])
def list_shares(
    report_id: int,
    founder: Founder = Depends(get_founder_record),
    db: Session = Depends(get_db),
) -> list[ShareOut]:
    """Every live link to this report.

    A founder cannot decide whether to revoke a link they cannot see. Shares
    were creatable and (as of the endpoint below) revocable, but never
    listable, so the only record of what had been shared was whatever the
    founder remembered sending.
    """
    _owned_report(db, founder, report_id)
    return [
        ShareOut.model_validate(s)
        for s in reports_repository.list_active_shares(
            db, founder_id=founder.founder_id, report_id=report_id,
        )
    ]


@router.delete("/{report_id}/share/{token}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_share(
    report_id: int, token: str,
    founder: Founder = Depends(get_founder_record),
    db: Session = Depends(get_db),
) -> Response:
    """Revoke a share link, immediately and permanently.

    Ownership is checked on the report AND on the share row (the repository
    scopes its update by founder_id), so a token belonging to someone else is a
    404 rather than a revocation. An unknown or already-revoked token is also a
    404 -- deliberately the same answer, so this cannot be used to probe which
    tokens exist, matching the shared endpoints' own rule.
    """
    _owned_report(db, founder, report_id)
    if not reports_repository.revoke_share(db, founder_id=founder.founder_id, token=token):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such share link.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
