"""Getting a founder their report PDF -- rendered once, kept, and never faked.

The export endpoint used to render on every download and fall back to a plain
reportlab document whenever Gotenberg was unreachable. Both paths return 200
with a real `application/pdf` body, so a founder who downloaded during a blip
received the wrong document and nothing ever tried again -- not the endpoint,
not a sweep, not an alert. It was the quietest failure in the product.

What replaces it:

  * a rendered PDF is STORED, so the second download is a fetch, not a render;
  * when the renderer is down there is NO substitute document. The request says
    so honestly and records that someone is waiting;
  * `backfill_pending_pdfs` picks those up later, so "in a few minutes" is a
    promise something actually keeps.

Storage is optional. `build_object_storage()` returns None with no bucket
configured (local dev, CI), and everything here still works -- the PDF is simply
rendered fresh each time instead of being kept. Storage makes downloads cheap
and durable; it is not what makes them correct.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.v1.reports.gotenberg import GotenbergError, render_pdf
from app.api.v1.reports.print_html import build_report_html
from app.core.config import settings
from app.core.logger import logger
from app.models.schema import FounderReports


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def storage_key(report_id: int) -> str:
    return f"reports/{report_id}/clarity-report.pdf"


def _storage():
    """The shared object store, or None when no bucket is configured.

    Never raises: a storage problem must not stop a founder getting a correctly
    rendered PDF, it only stops us keeping a copy of it.
    """
    try:
        from app.ai_chat.attachments.storage import build_object_storage

        return build_object_storage()
    except Exception as exc:  # noqa: BLE001 -- optional dependency, optional feature
        logger.warning("report pdf storage unavailable", exc_info=exc)
        return None


def stored_pdf(report: FounderReports) -> bytes | None:
    """The already-rendered PDF, if one was kept and is still retrievable."""
    if not report.pdf_storage_key:
        return None
    store = _storage()
    if store is None:
        return None
    try:
        return store.get(report.pdf_storage_key)
    except Exception as exc:  # noqa: BLE001
        # A missing or unreadable object is not an error the founder should see:
        # fall through and render again, which also repairs the stored copy.
        logger.warning(
            "stored report pdf could not be read; re-rendering",
            extra={"report_id": report.report_id, "key": report.pdf_storage_key},
            exc_info=exc,
        )
        return None


def render_and_store(db: Session, report: FounderReports, narrative) -> bytes | None:
    """Render this report's PDF and keep it. None when the renderer is down.

    None is a fact about the renderer, not a failure of this function -- the
    caller decides what to tell the founder. Nothing is written to the database
    on that path, so the request stays retryable.
    """
    try:
        pdf = render_pdf(build_report_html(narrative), base_url=settings.GOTENBERG_URL)
    except GotenbergError as exc:
        logger.warning(
            "gotenberg unavailable; no PDF produced",
            extra={"report_id": report.report_id, "url": settings.GOTENBERG_URL},
            exc_info=exc,
        )
        return None

    # Whatever happens to the copy, the founder is no longer waiting: rendering
    # works again, so their next download succeeds. Clearing this only when the
    # PUT also succeeded left the row pending forever wherever storage is not
    # configured, and the sweep re-rendered the same report on every pass.
    _clear_pending(db, report)

    store = _storage()
    if store is None:
        # Correct document, just not kept. Every later download re-renders.
        return pdf

    key = storage_key(report.report_id)
    try:
        store.put(key, pdf, content_type="application/pdf")
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "report pdf rendered but could not be stored; serving it anyway",
            extra={"report_id": report.report_id, "key": key},
            exc_info=exc,
        )
        return pdf

    try:
        report.pdf_storage_key = key
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        # The object is in the store; only the pointer failed. The founder still
        # gets their PDF, and the next download re-renders and re-points.
        logger.warning(
            "report pdf stored but the key could not be recorded",
            extra={"report_id": report.report_id, "key": key},
            exc_info=exc,
        )
    return pdf


def _clear_pending(db: Session, report: FounderReports) -> None:
    """Nobody is waiting on this report any more."""
    if report.pdf_requested_at is None:
        return
    try:
        report.pdf_requested_at = None
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        logger.warning(
            "could not clear a pending report PDF flag; the sweep will retry it",
            extra={"report_id": report.report_id},
            exc_info=exc,
        )


def mark_pdf_requested(db: Session, report: FounderReports) -> None:
    """Record that a founder tried to download and could not be served.

    Idempotent: the FIRST attempt's timestamp is kept, so the sweep processes
    the founder who has been waiting longest rather than the one who clicked
    most recently.
    """
    if report.pdf_requested_at is not None:
        return
    try:
        report.pdf_requested_at = _utcnow()
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        logger.error(
            "could not record a pending report PDF; the sweep will not pick it up",
            extra={"report_id": report.report_id},
            exc_info=exc,
        )


def backfill_pending_pdfs(db: Session, *, limit: int = 25) -> dict:
    """Render the PDFs founders are waiting on. Safe to run on any cadence.

    Only touches reports someone actually asked for -- most reports are never
    downloaded, and rendering all of them would spend Chromium time on documents
    nobody opens.

    One report's failure never stops the sweep, matching reconcile_reports: a
    single unrenderable report must not strand everybody behind it.
    """
    from app.api.v1.reports.routes import _build_narrative

    pending = db.execute(
        select(FounderReports)
        .where(
            FounderReports.pdf_requested_at.is_not(None),
            FounderReports.pdf_storage_key.is_(None),
            FounderReports.is_active.is_(True),
        )
        .order_by(FounderReports.pdf_requested_at.asc())
        .limit(limit)
    ).scalars().all()

    results = []
    for report in pending:
        try:
            narrative = _build_narrative(db, report)
            pdf = render_and_store(db, report, narrative)
            results.append({
                "report_id": report.report_id,
                "status": "rendered" if pdf else "renderer_unavailable",
            })
            if pdf is None:
                # Gotenberg is down for everyone, not for this row. Stop rather
                # than grinding through the whole batch to fail identically.
                logger.warning(
                    "backfill stopping early: renderer is unavailable",
                    extra={"pending": len(pending), "done": len(results)},
                )
                break
        except Exception as exc:  # noqa: BLE001 -- one report must not stop the sweep
            db.rollback()
            logger.error(
                "report pdf backfill failed for one report, continuing",
                extra={"report_id": report.report_id},
                exc_info=exc,
            )
            results.append({"report_id": report.report_id, "status": "failed",
                            "error": str(exc)})

    return {"pending_count": len(pending), "results": results}
