/**
 * services/invoices.js — the receipt a founder downloads after paying.
 *
 * The rule that shapes this whole file: THE BROWSER COMPUTES NOTHING ABOUT
 * MONEY. Every figure here — the amount, the discount, the tax split, even
 * whether a tax split exists at all — arrives already decided by the backend,
 * which read it back out of the `payments` row Razorpay actually charged
 * against. A receipt total assembled in JSX is a total that can disagree with
 * the one printed on the PDF, and the founder would have no way to tell which
 * of the two is real.
 *
 * That is also why the PDF is fetched rather than generated here. Client-side
 * PDF builders (jsPDF and friends) mean a second implementation of the layout
 * and a second implementation of the arithmetic, drifting from the server's;
 * the report export learned that lesson already. One template lives in
 * app/payments/invoice_html.py and both the screen and the file come out of it.
 */

import { get } from './api';

/**
 * This founder's billing history, newest first.
 *
 * Captured and refunded payments only — the backend refuses to list a pending
 * row, because an abandoned checkout shown as billing history reads as a
 * charge that was never made.
 *
 * @returns {Promise<Array<{payment_id:number, number:string, document_title:string,
 *   paid_at:string|null, status:string, description:string, billing_cycle:string,
 *   amount_inr:number, discount_inr:number|null, coupon_code:string|null,
 *   is_tax_invoice:boolean, tax:object|null}>>}
 */
export function listInvoices() {
  return get('/payments/invoices');
}

/** One receipt's details, without downloading the file. */
export function getInvoice(paymentId) {
  return get(`/payments/invoices/${paymentId}`);
}

/**
 * Download the receipt PDF.
 *
 * Rejects rather than resolving on failure. The endpoint answers 503 when the
 * PDF renderer is momentarily down, and that is a real "try again shortly" —
 * handing a founder a broken or substitute document for a financial record is
 * worse than telling them to wait. The message the API writes is the one the
 * founder should read, so it is dug back out of the error blob the same way
 * services/reports.js does it.
 */
export async function downloadInvoicePdf(paymentId, invoiceNumber) {
  let blob;
  try {
    blob = await get(`/payments/invoices/${paymentId}/pdf`, { responseType: 'blob' });
  } catch (err) {
    // responseType 'blob' applies to error responses too, so the API's own
    // founder-facing sentence arrives as an unread Blob and the generic
    // "Request failed with status code 503" wins. Read it back out.
    if (err?.data instanceof Blob) {
      try {
        const parsed = JSON.parse(await err.data.text());
        if (typeof parsed?.message === 'string') err.message = parsed.message;
      } catch { /* not JSON — keep the normalized message */ }
    }
    throw err;
  }

  // The document number, not the payment id: this is the name the file carries
  // into the founder's own accounts, and slashes are not legal in one.
  const safeName = (invoiceNumber || `receipt-${paymentId}`).replace(/\//g, '-');
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `${safeName}.pdf`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  // Next tick — revoking synchronously can cancel the download before the
  // browser has finished reading the blob.
  setTimeout(() => URL.revokeObjectURL(url), 0);
}
