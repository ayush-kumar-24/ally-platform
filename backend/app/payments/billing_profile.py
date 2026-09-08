"""Billing identity -- the name, GSTIN and address an invoice has to carry.

WHY IT IS SEPARATE FROM `founders`. A founder's product identity (who they
are, what plan they are on) and their billing identity (which legal entity is
being invoiced, at which address, under which GSTIN) are not the same thing
and do not change together. Most founders will never have one of these rows;
the ones who do are businesses claiming input credit, and for them the
details have to be right before an invoice is issued, not corrected after.

WHAT THIS DOES NOT DO. It computes no tax. It decides no place-of-supply
rule and applies no rate. Guide step 14 is explicit that the GST treatment,
the rate and whether Razorpay's document is a compliant tax invoice for this
use case are the CA's to confirm -- and a number this codebase invented would
be worse than the absence of one, because it would look authoritative. What
this module does is COLLECT and VALIDATE the inputs that answer needs.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.payments.errors import InvalidBillingProfileError

#: The real GSTIN shape: 2-digit state code, 10-character PAN, an entity
#: number, a literal 'Z', and a checksum character. Mirrored by a CHECK
#: constraint in migration e8a5c31d7f42 -- validated in both places on purpose,
#: so a bad value cannot arrive through a path that skips this service.
GSTIN_RE = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$")
PINCODE_RE = re.compile(r"^[0-9]{6}$")

#: The first two GSTIN characters are the state code. 01-38 are the states and
#: union territories; 97 is "other territory" and 99 is used for a foreign
#: holder. Checked separately from the format regex because '00XXXXX...' has
#: exactly the right shape and names no state -- the format check alone passes
#: it, and it would reach an invoice as a place of supply that does not exist.
_GSTIN_STATE_CODES = {f"{n:02d}" for n in range(1, 39)} | {"97", "99"}


@dataclass(frozen=True)
class BillingProfile:
    founder_id: int
    customer_type: str
    business_name: str | None
    gstin: str | None
    billing_address: str | None
    billing_city: str | None
    billing_state: str | None
    billing_pincode: str | None
    billing_country: str

    @property
    def is_invoice_ready(self) -> bool:
        """Enough here to put on a GST invoice.

        A business needs its name, GSTIN and place of supply; an individual
        needs an address and state. Exposed so the billing page can prompt for
        what is missing BEFORE the founder pays, rather than after -- a
        Razorpay invoice cannot be reissued against different details as
        easily as a form can be filled in.
        """
        if not (self.billing_address and self.billing_state and self.billing_pincode):
            return False
        if self.customer_type == "business":
            return bool(self.business_name and self.gstin)
        return True


class BillingProfileRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, founder_id: int) -> BillingProfile | None:
        row = self.db.execute(
            text("SELECT founder_id, customer_type, business_name, gstin, billing_address, "
                 "       billing_city, billing_state, billing_pincode, billing_country "
                 "FROM business_profiles WHERE founder_id = :fid"),
            {"fid": founder_id},
        ).mappings().first()
        if row is None:
            return None
        return BillingProfile(**dict(row))

    def upsert(self, founder_id: int, **fields) -> BillingProfile:
        """One row per founder, enforced by a unique constraint and written as
        an upsert -- editing billing details is the normal case, not the
        exception, and a second row would leave "which address do we invoice"
        genuinely ambiguous."""
        self.db.execute(
            text("INSERT INTO business_profiles "
                 "(founder_id, customer_type, business_name, gstin, billing_address, "
                 " billing_city, billing_state, billing_pincode, billing_country) "
                 "VALUES (:fid, :ctype, :bname, :gstin, :addr, :city, :state, :pin, :country) "
                 "ON CONFLICT (founder_id) DO UPDATE SET "
                 "  customer_type = EXCLUDED.customer_type, "
                 "  business_name = EXCLUDED.business_name, "
                 "  gstin = EXCLUDED.gstin, "
                 "  billing_address = EXCLUDED.billing_address, "
                 "  billing_city = EXCLUDED.billing_city, "
                 "  billing_state = EXCLUDED.billing_state, "
                 "  billing_pincode = EXCLUDED.billing_pincode, "
                 "  billing_country = EXCLUDED.billing_country, "
                 "  updated_at = now()"),
            {"fid": founder_id, "ctype": fields["customer_type"],
             "bname": fields.get("business_name"), "gstin": fields.get("gstin"),
             "addr": fields.get("billing_address"), "city": fields.get("billing_city"),
             "state": fields.get("billing_state"), "pin": fields.get("billing_pincode"),
             "country": fields.get("billing_country") or "IN"},
        )
        self.db.commit()
        return self.get(founder_id)


class BillingProfileService:
    def __init__(self, repository: BillingProfileRepository):
        self.repository = repository

    def get(self, founder_id: int) -> BillingProfile | None:
        return self.repository.get(founder_id)

    def save(self, founder_id: int, *, customer_type: str,
             business_name: str | None = None, gstin: str | None = None,
             billing_address: str | None = None, billing_city: str | None = None,
             billing_state: str | None = None, billing_pincode: str | None = None,
             billing_country: str = "IN") -> BillingProfile:
        """Normalise, validate, then write.

        Normalisation happens before validation and before storage so the
        stored value is canonical: a GSTIN typed in lower case with a stray
        space is the same GSTIN, and storing it verbatim would make it fail
        every later comparison for a reason the founder cannot see.
        """
        if customer_type not in ("individual", "business"):
            raise InvalidBillingProfileError(
                "customer type must be either 'individual' or 'business'")

        gstin = (gstin or "").strip().upper().replace(" ", "") or None
        business_name = (business_name or "").strip() or None
        billing_pincode = (billing_pincode or "").strip() or None
        billing_state = (billing_state or "").strip() or None

        if customer_type == "business" and not business_name:
            raise InvalidBillingProfileError("a business needs a registered name")

        if gstin is not None:
            if not GSTIN_RE.match(gstin):
                raise InvalidBillingProfileError(
                    "that GSTIN is not a valid 15-character GST number")
            if gstin[:2] not in _GSTIN_STATE_CODES:
                # Caught here rather than by the format regex: '00XXXXX...' is
                # the right shape and is not a state.
                raise InvalidBillingProfileError(
                    f"'{gstin[:2]}' is not a valid GST state code")
            if customer_type != "business":
                # A GSTIN belongs to a registered entity. Accepting one against
                # an "individual" profile would put a GSTIN on an invoice that
                # names no business, which is not a document anyone can use.
                raise InvalidBillingProfileError(
                    "a GSTIN belongs to a business -- switch the billing type to Business")

        if billing_pincode is not None and not PINCODE_RE.match(billing_pincode):
            raise InvalidBillingProfileError("a PIN code is exactly six digits")

        return self.repository.upsert(
            founder_id, customer_type=customer_type, business_name=business_name,
            gstin=gstin, billing_address=(billing_address or "").strip() or None,
            billing_city=(billing_city or "").strip() or None,
            billing_state=billing_state, billing_pincode=billing_pincode,
            billing_country=(billing_country or "IN").strip().upper()[:2],
        )
