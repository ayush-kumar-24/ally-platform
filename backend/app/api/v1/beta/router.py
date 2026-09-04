"""Public beta waitlist -- the one endpoint founders themselves touch.

    POST /beta/waitlist   join the list
    GET  /beta/waitlist/me   where an authenticated founder stands

Deliberately says almost nothing back. `POST` returns the same 202 whether the
address was new or already on the list, because a signup form that distinguishes
the two is an email-enumeration oracle: anyone could paste a list of addresses and
learn which ones are registered. The admin panel is where the real state lives.

For the same reason nothing here exposes queue position to an anonymous caller.
An authenticated founder can see their own standing via `/beta/waitlist/me`,
which is scoped to their own record and nobody else's.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, ConfigDict, Field

from app.api.deps import get_founder_record
from app.core.container import container
from app.db.session import get_db
from app.models import Founder

router = APIRouter(prefix="/beta", tags=["beta"])


class JoinRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # A plain str, validated by BetaAccessService.join. `EmailStr` would pull in
    # email-validator, which this project does not depend on, to buy a stricter
    # syntax check than actually matters -- the only address that is verified is
    # one that receives the invite.
    email: str = Field(min_length=3, max_length=200)
    full_name: str = Field(default="", max_length=120)


@router.post("/waitlist", status_code=status.HTTP_202_ACCEPTED, response_model=dict,
             summary="Join the beta waitlist")
def join_waitlist(payload: JoinRequest, db=Depends(get_db)) -> dict:
    container.beta_service(db).join(
        email=payload.email, full_name=payload.full_name, source="signup")
    # Same response either way -- see the module docstring.
    return {"status": "received",
            "message": "You're on the list. We'll email you when the next slot opens."}


@router.get("/waitlist/me", response_model=dict,
            summary="This founder's own waitlist standing")
def my_standing(founder: Founder = Depends(get_founder_record), db=Depends(get_db)) -> dict:
    """Their own row only. `times_deferred` is included because it is the thing
    that actually moves them up the queue -- showing it is what makes "you're next"
    a claim they can hold us to rather than a platitude."""
    service = container.beta_service(db)
    entry = service.repository.get_entry_by_email((founder.email or "").lower())
    if entry is None:
        return {"on_waitlist": False}
    return {
        "on_waitlist": True,
        "status": entry.status.value,
        "joined_at": entry.joined_at,
        "times_passed_over": entry.times_deferred,
        "invited_at": entry.invited_at,
        "coupon_code": entry.coupon_code if entry.status.value == "invited" else None,
    }
