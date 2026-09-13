"""Who a payment is for, and what an invoice for it needs.

The checkout screen asks one question before Pay -- personal use or business
use -- and, for a business, offers three optional fields: the company name, a
GSTIN and a billing address. A founder buying through their company needs
those on the invoice to claim input tax credit, and asking for them after the
payment means chasing them by email.

Nothing in here may fail a payment. Every field is optional, and a value that
does not survive validation is dropped rather than raising -- refusing the
whole checkout over a mistyped GSTIN would turn an invoicing convenience into
a barrier to paying. The frontend checks the same shapes while they are being
typed, which is where a correction actually helps; this module exists because
the frontend cannot be trusted with what ends up on the row.

Mirrors app/lib/billing.ts in the landing-page repo -- same shapes, same
rules -- so a founder who answered this question once, on the pricing page
before they had an account, sees a checkout screen that asks it the same way.
"""

from __future__ import annotations

import re
from typing import Any

_COMPANY_MAX = 120
_ADDRESS_MAX = 400
_GSTIN_LENGTH = 15

# State code, the holder's PAN, an entity number, 'Z', and a checksum
# character. The shape is checked, not the checksum -- a wrong checksum is a
# typo the accounts team will catch on the draft invoice, while a checksum
# implementation that is subtly wrong here would reject valid numbers with no
# way for the founder to argue.
_GSTIN_RE = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][0-9A-Z]Z[0-9A-Z]$")

_CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")
# Spares \n: an address is stored with the line breaks it was typed with.
_CONTROL_KEEP_NEWLINES_RE = re.compile(r"[\x00-\x09\x0b-\x1f\x7f]")


def _clean_text(value: Any, max_len: int, *, allow_newlines: bool = False) -> str | None:
    if not isinstance(value, str):
        return None
    if allow_newlines:
        collapsed = re.sub(r"\r\n?", "\n", value)
        collapsed = re.sub(r"[^\S\n]+", " ", collapsed)
        collapsed = re.sub(r"\n{3,}", "\n\n", collapsed)
        collapsed = _CONTROL_KEEP_NEWLINES_RE.sub("", collapsed)
    else:
        collapsed = re.sub(r"\s+", " ", value)
        collapsed = _CONTROL_RE.sub("", collapsed)
    s = collapsed.strip()[:max_len].strip()
    return s or None


def normalize_gstin(value: Any) -> str | None:
    """Uppercased and stripped of the spaces and dashes people type into it."""
    if not isinstance(value, str):
        return None
    s = re.sub(r"[\s-]", "", value).upper()
    if len(s) != _GSTIN_LENGTH or not _GSTIN_RE.match(s):
        return None
    return s


def parse_billing(value: Any) -> dict | None:
    """Validates what the checkout screen sent. None when there is nothing
    worth keeping, so a founder who never touched the toggle is recorded as
    not having answered the question at all -- not as having chosen personal
    use."""
    if not isinstance(value, dict):
        return None
    use = "business" if value.get("use") == "business" else "personal"

    if use == "personal":
        return {"v": 1, "use": "personal"}

    out: dict[str, Any] = {"v": 1, "use": "business"}
    company = _clean_text(value.get("company"), _COMPANY_MAX)
    gstin = normalize_gstin(value.get("gstin"))
    address = _clean_text(value.get("address"), _ADDRESS_MAX, allow_newlines=True)
    if company:
        out["company"] = company
    if gstin:
        out["gstin"] = gstin
    if address:
        out["address"] = address
    return out


def describe_billing(billing: dict | None) -> str:
    """One line for logs and support -- what the accounts team is invoicing."""
    if not billing:
        return "not stated"
    if billing.get("use") != "business":
        return "personal use"
    parts = [
        billing.get("company"),
        f"GSTIN {billing['gstin']}" if billing.get("gstin") else None,
        billing.get("address", "").replace("\n", ", ") if billing.get("address") else None,
    ]
    parts = [p for p in parts if p]
    return f"business use · {' · '.join(parts)}" if parts else "business use (no invoice details given)"
