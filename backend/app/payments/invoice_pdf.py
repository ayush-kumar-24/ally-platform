"""Getting a founder their receipt PDF -- rendered once, kept, never faked.

The same three rules `reports/pdf_delivery.py` arrived at, for the same
reasons, and one extra that only applies to money:

  * a rendered PDF is STORED, so the second download is a fetch, not a render;
  * when the renderer is down there is NO substitute document -- the request
    says so honestly and the founder retries;
  * storage is optional. With no bucket configured (local dev, CI) everything
    here still works, it just re-renders each time. Storage makes downloads
    cheap, it is not what makes them correct.

The extra rule: THE STORED COPY IS THE DOCUMENT. A receipt is not regenerated
content the way a report narrative is -- it is a record of a transaction, and
a founder who downloads the same receipt in March and in November must get the
same bytes. So once a PDF exists for a payment it is served, never re-rendered
because the template got prettier in between. Only an unreadable or missing
object falls through to a fresh render.
"""

from __future__ import annotations

from app.core.config import settings
from app.core.logger import logger
from app.api.v1.reports.gotenberg import GotenbergError, render_pdf
from app.payments.invoice import Invoice
from app.payments.invoice_html import build_invoice_html


def storage_key(payment_id: int) -> str:
    return f"invoices/{payment_id}/invoice.pdf"


def _storage():
    """The shared object store, or None when no bucket is configured.

    Never raises: a storage problem must not stop a founder getting a correctly
    rendered receipt, it only stops us keeping a copy of it.
    """
    try:
        from app.services.object_storage import build_object_storage

        return build_object_storage()
    except Exception as exc:  # noqa: BLE001 -- optional dependency, optional feature
        logger.warning("invoice pdf storage unavailable", exc_info=exc)
        return None


def stored_pdf(key: str | None) -> bytes | None:
    """The already-rendered receipt, if one was kept and is still retrievable."""
    if not key:
        return None
    store = _storage()
    if store is None:
        return None
    try:
        return store.get(key)
    except Exception as exc:  # noqa: BLE001
        # A missing or unreadable object is not an error the founder should
        # see: fall through and render again, which also repairs the copy.
        logger.warning("stored invoice pdf could not be read; re-rendering",
                       extra={"key": key}, exc_info=exc)
        return None


class InvoiceRendererUnavailable(RuntimeError):
    """Gotenberg is down. The receipt exists, this request just cannot make a
    PDF of it -- which is a "try again shortly", not a failed payment, and the
    route must say so in those terms."""


def render_and_store(repository, invoice: Invoice, *, payment_id: int,
                     founder_id: int) -> bytes:
    """Render this payment's receipt and keep it. Raises when the renderer is down.

    Unlike the report equivalent this raises rather than returning None: there
    is no queue to put the founder in and no sweep to pick them up, because a
    receipt needs no narrative generated first -- the retry is simply pressing
    the button again once Chromium is back.
    """
    try:
        pdf = render_pdf(build_invoice_html(invoice), base_url=settings.GOTENBERG_URL)
    except GotenbergError as exc:
        logger.warning("gotenberg unavailable; no invoice PDF produced",
                       extra={"payment_id": payment_id, "url": settings.GOTENBERG_URL},
                       exc_info=exc)
        raise InvoiceRendererUnavailable(str(exc)) from exc

    # Written before the PDF is stored and independently of whether storing
    # works: the number is now on a document a founder is holding, so it has to
    # be the number we have on file, storage or no storage. First-write-wins in
    # the repository keeps this idempotent.
    try:
        repository.record_invoice_number(payment_id, founder_id=founder_id,
                                         number=invoice.number)
    except Exception as exc:  # noqa: BLE001 -- the founder still gets the PDF
        logger.error("invoice rendered but its number could not be recorded",
                     extra={"payment_id": payment_id, "number": invoice.number},
                     exc_info=exc)

    store = _storage()
    if store is None:
        # Correct document, just not kept. Every later download re-renders.
        return pdf

    key = storage_key(payment_id)
    try:
        store.put(key, pdf, content_type="application/pdf")
    except Exception as exc:  # noqa: BLE001
        logger.warning("invoice pdf rendered but could not be stored; serving it anyway",
                       extra={"payment_id": payment_id, "key": key}, exc_info=exc)
        return pdf

    try:
        repository.record_invoice_url(payment_id, founder_id=founder_id, url=key)
    except Exception as exc:  # noqa: BLE001
        # The object is in the store; only the pointer failed. The founder
        # still gets their PDF, and the next download re-renders and re-points.
        logger.warning("invoice pdf stored but the key could not be recorded",
                       extra={"payment_id": payment_id, "key": key}, exc_info=exc)
    return pdf


def get_or_render_pdf(repository, invoice: Invoice, *, payment_id: int,
                      founder_id: int) -> bytes:
    """Serve the stored receipt, else render and keep it."""
    key = repository.invoice_storage_key(payment_id, founder_id=founder_id)
    pdf = stored_pdf(key)
    if pdf is not None:
        return pdf
    return render_and_store(repository, invoice, payment_id=payment_id,
                            founder_id=founder_id)
