"""The invoice as a self-contained print document.

Self-contained is the requirement, not a preference: Gotenberg renders this in
a headless Chromium with no network of its own (see reports/gotenberg.py), so
an external stylesheet, webfont or logo URL would silently render as nothing.
Everything here is inline, and the type is system fonts on purpose -- a receipt
does not need the report's embedded display face, and not embedding it keeps
the PDF small enough to email.

The same HTML is also served to the browser, which is what keeps the on-screen
receipt and the downloaded PDF from drifting: there is one template, not a JSX
copy of one. That drift is the exact failure reports/print_html.py was written
to prevent, and there is no reason to relearn it here.
"""

from __future__ import annotations

from decimal import Decimal
from html import escape

from app.payments.invoice import Invoice

_CSS = """
@page{size:A4;margin:16mm 14mm;}
*{box-sizing:border-box;}
body{margin:0;background:#fff;color:#14261c;
  font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;
  font-size:12px;line-height:1.5;-webkit-print-color-adjust:exact;print-color-adjust:exact;}
.doc{max-width:186mm;margin:0 auto;}
.top{display:flex;justify-content:space-between;align-items:flex-start;
  border-bottom:2px solid #1B4332;padding-bottom:14px;margin-bottom:20px;}
.brand{font-size:19px;font-weight:700;color:#1B4332;letter-spacing:-.2px;}
.brand .sub{display:block;font-size:11px;font-weight:400;color:#556458;
  margin-top:4px;white-space:pre-line;letter-spacing:0;}
.docmeta{text-align:right;}
.doctitle{font-size:15px;font-weight:700;text-transform:uppercase;
  letter-spacing:1.4px;color:#1B4332;}
.docmeta dl{margin:8px 0 0;display:grid;grid-template-columns:auto auto;
  gap:2px 10px;font-size:11px;}
.docmeta dt{color:#556458;text-align:right;margin:0;}
.docmeta dd{margin:0;font-weight:600;text-align:right;}
.parties{display:flex;gap:18px;margin-bottom:20px;}
.party{flex:1;background:#f4f7f4;border-radius:7px;padding:12px 14px;}
.party h2{margin:0 0 6px;font-size:10px;text-transform:uppercase;
  letter-spacing:1.1px;color:#556458;font-weight:700;}
.party .name{font-weight:700;font-size:13px;}
.party .line{color:#3c4b41;word-break:break-word;}
table.items{width:100%;border-collapse:collapse;margin-bottom:16px;}
table.items th{background:#1B4332;color:#fff;font-size:10px;text-transform:uppercase;
  letter-spacing:.9px;padding:8px 10px;text-align:left;font-weight:600;}
table.items td{padding:11px 10px;border-bottom:1px solid #e2e8e4;vertical-align:top;}
table.items .num{text-align:right;white-space:nowrap;}
.desc-sub{display:block;color:#556458;font-size:11px;margin-top:3px;}
.totals{margin-left:auto;width:74mm;}
.totals .row{display:flex;justify-content:space-between;gap:16px;padding:5px 0;}
.totals .row.muted{color:#556458;}
.totals .row.discount{color:#1f7a4d;}
.totals .grand{border-top:2px solid #1B4332;margin-top:6px;padding-top:9px;
  font-size:15px;font-weight:700;color:#1B4332;}
.paid{margin-top:14px;display:inline-block;background:#e7f5ec;color:#186a43;
  border-radius:999px;padding:5px 13px;font-size:11px;font-weight:700;
  text-transform:uppercase;letter-spacing:.8px;}
.paid.refunded{background:#fdf0e6;color:#9a5312;}
.note{margin-top:26px;padding-top:12px;border-top:1px solid #e2e8e4;
  color:#6a7a70;font-size:10.5px;line-height:1.6;}
.note strong{color:#3c4b41;}
"""


def _rupees(amount: Decimal) -> str:
    """`12,345.00` -- Indian digit grouping, done here because Python's
    locale module cannot be relied on inside a container image that carries no
    locales. Two decimals always: a receipt showing `499` next to `499.00`
    elsewhere reads like two different numbers."""
    sign = "-" if amount < 0 else ""
    whole, _, frac = f"{abs(amount):.2f}".partition(".")
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        whole = ",".join(parts + [tail])
    return f"{sign}{whole}.{frac}"


def _pct(value: Decimal) -> str:
    """`18`, not `18.0` -- and `2.5` when the rate really has a half.

    Decimal's `:g` keeps the trailing zero that the rate was configured with,
    which reads as a precision the tax rate does not have.
    """
    return f"{value.normalize():f}".rstrip("0").rstrip(".") or "0"


def _money(symbol: str, amount: Decimal) -> str:
    return f"{symbol}{_rupees(amount)}"


def _date(value) -> str:
    return value.strftime("%d %b %Y") if value else "—"


def _rows(pairs: list[tuple[str, str]]) -> str:
    return "".join(
        f"<dt>{escape(k)}</dt><dd>{escape(v)}</dd>" for k, v in pairs if v
    )


def build_invoice_html(invoice: Invoice) -> str:
    """Render one Invoice to a complete HTML document."""
    symbol = "₹" if (invoice.currency or "INR").upper() == "INR" else ""
    tax = invoice.tax

    meta = _rows([
        ("Invoice No.", invoice.number),
        ("Date", _date(invoice.issued_at)),
        ("Payment ID", invoice.payment_reference or ""),
        ("Order ID", invoice.order_reference or ""),
    ])

    seller_lines = [invoice.seller_address, invoice.seller_email]
    if invoice.seller_gstin:
        seller_lines.append(f"GSTIN: {invoice.seller_gstin}")
    if invoice.seller_state:
        seller_lines.append(f"State: {invoice.seller_state}")
    seller_block = "".join(
        f'<div class="line">{escape(line)}</div>' for line in seller_lines if line
    )

    # The SAC column appears only on a tax invoice. A receipt claims no tax
    # classification, so printing a service code on it would imply one.
    sac_head = "<th>SAC</th>" if invoice.sac_code else ""
    sac_cell = f"<td>{escape(invoice.sac_code)}</td>" if invoice.sac_code else ""

    # What the line item is worth BEFORE tax on a tax invoice, and simply what
    # was charged on a receipt. Two names for the column would be clearer still,
    # but one number that changes meaning silently would not -- hence the
    # heading below changes with it.
    line_amount = tax.taxable_value if tax else invoice.gross_amount
    amount_head = "Taxable value" if tax else "Amount"

    totals = []
    if invoice.list_amount is not None:
        totals.append(f'<div class="row muted"><span>Plan price</span>'
                      f'<span>{_money(symbol, invoice.list_amount)}</span></div>')
    if invoice.discount is not None:
        label = "Discount"
        if invoice.coupon_code:
            label = f"Discount ({invoice.coupon_code})"
        totals.append(f'<div class="row discount"><span>{escape(label)}</span>'
                      f'<span>−{_money(symbol, invoice.discount)}</span></div>')
    if tax:
        totals.append(f'<div class="row"><span>Taxable value</span>'
                      f'<span>{_money(symbol, tax.taxable_value)}</span></div>')
        half = _pct(tax.percent / 2)
        if tax.intra_state:
            totals.append(f'<div class="row muted"><span>CGST @ {half}%</span>'
                          f'<span>{_money(symbol, tax.cgst)}</span></div>')
            totals.append(f'<div class="row muted"><span>SGST @ {half}%</span>'
                          f'<span>{_money(symbol, tax.sgst)}</span></div>')
        else:
            totals.append(f'<div class="row muted"><span>IGST @ {_pct(tax.percent)}%</span>'
                          f'<span>{_money(symbol, tax.igst)}</span></div>')

    refunded = invoice.status == "refunded"
    badge = ("Refunded" if refunded else "Paid in full")
    badge_class = "paid refunded" if refunded else "paid"

    # The one sentence that has to be on a receipt with no GSTIN: it says what
    # the document IS, so nobody files a payment receipt as a tax invoice.
    tax_note = (
        "This is a computer-generated tax invoice and does not require a signature. "
        f"The amount shown is inclusive of GST at {_pct(tax.percent)}%."
        if tax else
        "This is a computer-generated payment receipt and does not require a "
        "signature. It is a record of payment, not a tax invoice, and no GST "
        "has been charged or is claimable against it."
    )

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>{escape(invoice.document_title)} {escape(invoice.number)}</title>
<style>{_CSS}</style></head>
<body><div class="doc">

  <div class="top">
    <div class="brand">{escape(invoice.seller_name)}<span class="sub">{seller_block}</span></div>
    <div class="docmeta">
      <div class="doctitle">{escape(invoice.document_title)}</div>
      <dl>{meta}</dl>
    </div>
  </div>

  <div class="parties">
    <div class="party">
      <h2>Billed to</h2>
      <div class="name">{escape(invoice.buyer_name or "—")}</div>
      <div class="line">{escape(invoice.buyer_email or "")}</div>
    </div>
    <div class="party">
      <h2>Payment</h2>
      <div class="name">{escape(invoice.billing_cycle)}</div>
      <div class="line">Paid on {escape(_date(invoice.paid_at))} · Razorpay</div>
    </div>
  </div>

  <table class="items">
    <thead><tr>
      <th>Description</th>{sac_head}<th class="num">{amount_head}</th>
    </tr></thead>
    <tbody><tr>
      <td>
        {escape(invoice.description)}
        <span class="desc-sub">{escape(invoice.billing_cycle)}</span>
      </td>
      {sac_cell}
      <td class="num">{_money(symbol, line_amount)}</td>
    </tr></tbody>
  </table>

  <div class="totals">
    {''.join(totals)}
    <div class="row grand"><span>Total paid</span>
      <span>{_money(symbol, invoice.gross_amount)}</span></div>
  </div>

  <span class="{badge_class}">{badge}</span>

  <div class="note">
    <strong>{escape(invoice.seller_name)}</strong> · {escape(invoice.seller_email or "")}<br>
    {escape(tax_note)}
  </div>

</div></body></html>"""
