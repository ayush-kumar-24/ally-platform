"""The public waitlist form's endpoint -- the one route in this API that
anybody on the internet may POST to without a token.

The waitlist site (join.goxlally.ai, a separate codebase) posts its form here.
Nothing is created but a `pending` row; access is granted only by an admin
approving it in the panel -- OR, while direct capacity is open (see
GET /capacity below), by signing in directly, no queue. Both paths converge
on the same founders row through services/provisioning.py.

WHY IT ALWAYS RETURNS THE SAME THING
202 with a fixed body, whether the row was inserted, was a duplicate, or
belongs to someone already approved. An endpoint that distinguishes those
cases tells an anonymous caller whether a given address is on the founder
list, which is an enumeration oracle over exactly the people we are trying to
be careful with. `register()` swallows the conflict for the same reason -- see
its docstring.

ABUSE PROTECTION, for an unauthenticated write:
  1. A per-IP rate limit, which stops one person scripting the form.
  2. A honeypot field no human ever fills in, which stops the commodity bots
     that submit every form they find. Filled means silently accepted and
     discarded -- a bot told it failed just tries again with a different shape.
  3. Length caps on every field, enforced by the schema, so the table cannot
     be used as free storage.

There is no CAPTCHA. It would be the fourth layer on a form whose worst case is
junk rows in a queue a human reads anyway, and it costs every genuine founder a
puzzle at the first moment they meet us.

ONE EXEMPTION FROM THE PER-IP LIMIT
The join.goxlally.ai landing site forwards its own registrations here
server-to-server (not from the visitor's browser), so every registration it
sends arrives from that site's own small pool of serverless egress IPs -- to
this endpoint's rate limiter, indistinguishable from one caller hammering it.
Five genuine founders registering within the same five minutes would cost the
sixth their registration, silently, on a launch day that is exactly when it is
most likely to happen.

A caller presenting X-Waitlist-Forward-Secret matching WAITLIST_FORWARD_SECRET
skips the per-IP bucket. This is not authentication -- the endpoint stays
unauthenticated by design, see above -- it only tells this one known,
server-to-server caller apart from "traffic from an IP" so its volume is not
double-limited under a limit meant to catch a single scripting visitor. The
landing site enforces its own real per-visitor limit before it ever reaches
here (its RATE_LIMIT/RATE_WINDOW_MS); honeypot and length caps still apply to
every request regardless of the header.
"""

from __future__ import annotations

import hmac

from fastapi import APIRouter, Depends, Header, Request, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.middleware.rate_limit import ip_rate_limit
from app.services.waitlist import register

router = APIRouter(prefix="/waitlist", tags=["waitlist"])

# Named at module level, not inline, so tests can override it -- same reason as
# the auth router's limiters (FastAPI keys dependency_overrides on the exact
# callable object, and a factory call makes a new closure every time).
_waitlist_ip_rate_limit = ip_rate_limit(key="waitlist-register", limit=5, window_seconds=300)


def waitlist_rate_limit(
    request: Request,
    x_waitlist_forward_secret: str | None = Header(default=None),
) -> None:
    """The per-IP limit, unless the one known forwarding caller identifies
    itself -- see the module docstring's "ONE EXEMPTION" section.

    `compare_digest`, not `==`: this compares a value an outside caller
    supplies against a stored secret, so it gets the same timing-safe
    comparison as the payment webhook signatures (app/payments/gateway.py)
    rather than the plain `!=` the internal-jobs secret uses -- that one is
    never compared against attacker-controlled input on a public route the
    way this is.

    Fails closed the same way INTERNAL_JOBS_SECRET does: an unset
    WAITLIST_FORWARD_SECRET makes `compare_digest` compare against an empty
    string, which a request cannot supply (the header check above already
    requires a non-None value), so the limiter is never skipped just because
    someone forgot to configure this.
    """
    secret = settings.WAITLIST_FORWARD_SECRET
    if secret and x_waitlist_forward_secret and hmac.compare_digest(
        x_waitlist_forward_secret, secret
    ):
        return
    _waitlist_ip_rate_limit(request)


class WaitlistSubmission(BaseModel):
    # extra="forbid" so a field the waitlist site adds without telling us fails
    # loudly here rather than being silently dropped for months.
    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=3, max_length=255)
    full_name: str = Field(min_length=1, max_length=200)
    company: str | None = Field(default=None, max_length=200)
    role_title: str | None = Field(default=None, max_length=120)
    stage: str | None = Field(default=None, max_length=60)
    note: str | None = Field(default=None, max_length=2000)
    source: str | None = Field(default=None, max_length=60)

    #: Honeypot. Rendered hidden on the form, so a human never sees it and a
    #: bot filling every input does. Named plausibly on purpose -- "honeypot"
    #: in the DOM defeats the point.
    website: str | None = Field(default=None, max_length=200)

    @field_validator("email")
    @classmethod
    def _looks_like_an_address(cls, value: str) -> str:
        """A shape check, not RFC 5322.

        Deliberately not pydantic's EmailStr: that pulls in `email-validator`,
        a dependency this project does not have and does not want for one
        field -- the same reasoning that keeps it off an auth library and off
        every vendor SDK. Nothing here is the real gate anyway. Supabase
        validates the address properly when the identity is created, and a
        human reads the row before that happens; this only keeps obvious
        rubbish out of the queue.
        """
        value = value.strip()
        local, sep, domain = value.partition("@")
        if not sep or not local or "." not in domain or domain.startswith(".") \
                or domain.endswith(".") or " " in value:
            raise ValueError("That does not look like an email address.")
        return value


class WaitlistAccepted(BaseModel):
    detail: str


class DirectSignupCapacityOut(BaseModel):
    #: Whether a stranger can sign in right now and get an account with no
    #: queue. The landing page's own CTA reads this to decide between
    #: "Register" and "Log in" -- but it is a courtesy, not the gate: the
    #: real one is in services/provisioning.py, at the point a founders row
    #: would actually be created, which this number cannot itself bypass.
    open: bool
    #: How many direct places are left. Not sensitive -- it is the same fact
    #: "open" already implies a non-zero version of, shown so a caller can
    #: read "3 left" rather than only yes/no.
    remaining: int


_ACCEPTED = WaitlistAccepted(
    detail="Thanks -- your registration is in. We review the founder's list by hand, "
           "and you'll get an email as soon as your place is confirmed."
)


@router.post(
    "",
    response_model=WaitlistAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(waitlist_rate_limit)],
)
def submit_registration(
    payload: WaitlistSubmission,
    request: Request,
    db: Session = Depends(get_db),
):
    """Join the waitlist. Always 202 -- see the module docstring."""
    if payload.website:
        # A bot. Accepted and dropped: an error response is a signal it can
        # iterate against, and a 202 is not.
        return _ACCEPTED

    register(
        db,
        email=str(payload.email),
        full_name=payload.full_name,
        company=payload.company,
        role_title=payload.role_title,
        stage=payload.stage,
        note=payload.note,
        source=payload.source,
        ip_address=request.client.host if request.client else None,
        # Truncated: the column is unbounded text and a crafted 100kB header
        # should not become a 100kB row.
        user_agent=(request.headers.get("user-agent") or "")[:500] or None,
    )
    return _ACCEPTED


@router.get("/capacity", response_model=DirectSignupCapacityOut)
def read_direct_signup_capacity(db: Session = Depends(get_db)):
    """Is a stranger allowed to sign in right now with no queue?

    Public and unauthenticated, like the rest of this router -- the landing
    page's own login/register CTA reads this before a visitor has any
    identity to authenticate with. Cheap and cacheable (a single-row SELECT,
    no write, no per-IP limit needed the way the POST above has one): the
    worst case of hammering this is a few extra reads of one integer.
    """
    remaining = db.execute(
        text("SELECT remaining FROM direct_signup_capacity WHERE id = true")
    ).scalar_one()
    return DirectSignupCapacityOut(open=remaining > 0, remaining=remaining)
