"""Server-side record of a founder's cookie choice.

WHY THIS EXISTS. The banner already ENFORCES the choice correctly -- rejecting
non-essential genuinely stops analytics and marketing scripts loading, and that
part was never broken. What was missing is the other half: the choice lived only
in the browser's localStorage, so it was per-device, wiped by clearing site data,
and impossible to produce later. Under the DPDP Act a Data Fiduciary has to be
able to DEMONSTRATE consent; "the user's laptop knew" is not a record.

The `cookie_preferences` table has existed, fully migrated, since the schema was
built -- with columns for each category, the banner action, a founder link and
timestamps. Nothing ever wrote a single row to it.

WHY IT NEEDS A SESSION. The table is founder-scoped under row-level security,
so an anonymous insert has no founder to attach to and would be refused. The
banner appears before sign-in, so this mirrors the pattern the terms consent
already uses: hold the choice locally, flush it when a session exists. What the
founder ticked, and WHEN they ticked it, is preserved -- `chosen_at` comes from
the client for exactly that reason, while `created_at` records when we stored it.

APPEND-ONLY. Every change of mind is a new row. A consent record that can be
overwritten cannot answer "what did they choose in March", which is the only
question it is ever asked.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.api.deps import client_ip, get_founder_record
from app.db.session import get_db
from app.models import Founder
from app.models.schema import CookiePreferences

router = APIRouter(prefix="/cookie-preferences", tags=["consents"])

#: What the banner offers. Mirrors the CHECK constraint on the table.
_ACTIONS = {"accepted_all", "rejected_all", "customised"}


class CookieChoice(BaseModel):
    """The categories the founder agreed to, as the banner recorded them."""

    model_config = ConfigDict(extra="forbid")

    analytics: bool = False
    marketing: bool = False
    functional: bool = False
    banner_action: str = "customised"
    #: When the founder actually clicked, which may be well before this reaches
    #: us -- the banner can be answered before sign-in. Optional: a client that
    #: does not send it simply gets the server time.
    chosen_at: datetime | None = None


class CookieChoiceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    preference_id: int
    necessary: bool
    analytics: bool
    marketing: bool
    functional: bool
    banner_action: str | None = None
    created_at: datetime | None = None


@router.post("", response_model=CookieChoiceRead, status_code=status.HTTP_201_CREATED)
async def record_cookie_choice(
    payload: CookieChoice,
    founder: Founder = Depends(get_founder_record),
    db: Session = Depends(get_db),
    ip: str | None = Depends(client_ip),
):
    """Store one cookie choice against the founder. Always appends.

    `necessary` is always true and is not taken from the client: essential
    cookies are what keeps someone signed in, they are not consented to, and
    accepting a client's `false` would record a choice we do not honour and
    could not honour.
    """
    action = payload.banner_action if payload.banner_action in _ACTIONS else "customised"

    row = CookiePreferences(
        founder_id=founder.founder_id,
        necessary=True,
        analytics=bool(payload.analytics),
        marketing=bool(payload.marketing),
        functional=bool(payload.functional),
        banner_action=action,
        banner_shown=True,
        # Server-resolved, never from the body -- the same rule the terms
        # consent follows, and for the same reason: a self-reported address
        # proves nothing.
        ip_address=ip,
        created_at=payload.chosen_at,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.get("", response_model=CookieChoiceRead | None)
async def read_cookie_choice(
    founder: Founder = Depends(get_founder_record),
    db: Session = Depends(get_db),
):
    """The founder's most recent choice, or null if they have never made one.

    Read back so the preferences screen can show what is currently stored rather
    than what this particular browser happens to remember.
    """
    return (
        db.query(CookiePreferences)
        .filter(CookiePreferences.founder_id == founder.founder_id)
        .order_by(CookiePreferences.preference_id.desc())
        .first()
    )
