"""The public waitlist form's endpoint -- the one route in this API that
anybody on the internet may POST to without a token.

The waitlist site (join.goxlally.ai, a separate codebase) posts its form here.
Nothing is created but a `pending` row; access is granted only by an admin
approving it in the panel.

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
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.middleware.rate_limit import ip_rate_limit
from app.services.waitlist import register

router = APIRouter(prefix="/waitlist", tags=["waitlist"])

# Named at module level, not inline, so tests can override it -- same reason as
# the auth router's limiters (FastAPI keys dependency_overrides on the exact
# callable object, and a factory call makes a new closure every time).
waitlist_rate_limit = ip_rate_limit(key="waitlist-register", limit=5, window_seconds=300)


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
