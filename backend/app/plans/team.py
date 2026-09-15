"""The team's own accounts, and why they are Pro wherever they are read.

THE PROBLEM. The people who build Ally use it on ordinary accounts, on
whatever tier those accounts happen to carry -- mostly Free. Every gate in the
product then applies to them exactly as it applies to a founder who has not
paid: Vision is closed, voice chat is closed, Know My Energy is closed, and
until the testing-phase grant, so was every email the product sends. A feature
nobody on the team can reach is a feature nobody on the team is testing, and
the reminder emails proved the point -- the delivery half of Plan Your Day
could not be checked by the people who wrote it.

WHY THIS CHANGES THE STORED TIER rather than wrapping every gate.

`founder.plan_type` is read in roughly a dozen places -- chat's quota gate,
planning, vision, voice, discovery's priority lead, the entitlement gates
dependency, the diagnosis service, the plans API, and both email paths. A
"team override" consulted at each of those is a rule with twelve chances to be
forgotten, and the thirteenth reader added next month gets it wrong silently.
Writing `pro` to the row instead means every one of those reads the right
answer without knowing this module exists, including the two that matter most
here: `send_due_reminders` and `send_pending_notification_emails` run in a
scheduled job with no request and no founder session, so a request-scoped
override would never have reached them at all.

TWO MECHANISMS, DELIBERATELY BOTH:

  * a data migration backfills every team account that already exists, so this
    is true the moment it deploys rather than the next time each person
    happens to sign in -- which matters because the jobs above run whether
    anyone is signed in or not;
  * `ensure_team_plan` re-applies it on any request that loads the founder, so
    a team member who registers later, or whose tier is changed by hand in the
    admin panel, is corrected without anyone remembering to.

WHAT THIS DOES NOT DO. Pro is every FEATURE, not every LIMIT. The 8,000/day
token ceiling and the one-diagnosis-per-account cap still apply; they are cost
controls with their own reasons, and the admin panel already carries a
diagnosis reset. Lifting those is a separate decision from "can the team reach
the feature at all", which is what this answers.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logger import logger
from app.plans.catalog import PlanTier

#: The tier a team account is held at. Pro is the whole feature set -- _BASE |
#: _WORKSPACE | _ADVISOR is every member of the Feature enum -- so there is no
#: "team" tier to invent and no plan to keep in step with the real ones.
TEAM_TIER = PlanTier.PRO.value


def is_team_email(email: str | None) -> bool:
    """Is this one of the team's own accounts?

    Case- and whitespace-insensitive: the list is maintained by hand and a
    stray capital must not quietly cost somebody their access.
    """
    if not email:
        return False
    return email.strip().lower() in settings.team_full_access_emails


def ensure_team_plan(db: Session, founder) -> bool:
    """Hold a team account at Pro. Returns True when it changed something.

    Best-effort by design, and never raises. This runs on the path that loads
    the founder for a request, so a failure here -- a row-level policy that
    declines the update, a read-only replica, a connection that has already
    gone bad -- must cost the founder nothing more than the access they
    already had. It is logged rather than swallowed silently, because a team
    account that is quietly NOT being upgraded is the one thing this module
    exists to prevent, and the migration is the belt to this brace.
    """
    if founder is None or not is_team_email(getattr(founder, "email", None)):
        return False
    if getattr(founder, "plan_type", None) == TEAM_TIER:
        return False                      # already correct; no write, no flush

    previous = getattr(founder, "plan_type", None)
    try:
        founder.plan_type = TEAM_TIER
        db.commit()
    except Exception as exc:              # noqa: BLE001 -- see the docstring
        db.rollback()
        logger.warning(
            "could not hold team account at pro",
            extra={"founder_id": getattr(founder, "founder_id", None),
                   "path": f"from={previous!r}"},
            exc_info=exc,
        )
        return False

    logger.info(
        "team account held at pro",
        extra={"founder_id": getattr(founder, "founder_id", None),
               "path": f"from={previous!r}"},
    )
    return True
