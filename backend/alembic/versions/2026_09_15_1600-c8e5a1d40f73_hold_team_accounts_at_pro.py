"""hold the team's own accounts at pro

Revision ID: c8e5a1d40f73
Revises: 719a012becf1
Create Date: 2026-09-15 16:00:00

The people who build Ally use it on ordinary accounts, mostly Free, so every
gate in the product applied to them exactly as it applies to a founder who has
not paid -- Vision closed, voice chat closed, Know My Energy closed, and the
emails the product sends among them. A feature nobody on the team can reach is
a feature nobody on the team is testing.

app/plans/team.py re-applies this on any request that loads the founder, which
covers anyone who registers later. This migration is what makes it true for the
accounts that already exist, and it is here rather than left to that path
because the two things most worth testing -- send_due_reminders and
send_pending_notification_emails -- run in a scheduled job with no request and
no session behind it. They read whatever is stored, so it has to be stored.

Matched on lower(email) and scoped to accounts that are not already pro, which
makes it idempotent: re-running changes nothing, and a team member who has
genuinely paid is left alone rather than being "upgraded" to what they have.

The list is duplicated here rather than imported from settings on purpose. A
data migration records what was intended ON THE DAY IT RAN; importing the live
list would mean this migration does something different every time the config
changes, which is the one thing a migration must never do.

NO DOWNGRADE. Nothing records what each account's tier was beforehand, so a
reversal would have to guess -- and guessing "free" would strip a genuine
subscription from anyone on the list who has one. Removing an address from
TEAM_FULL_ACCESS_EMAILS stops it being re-applied; correcting a tier after
that is an admin-panel action, not a schema one.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "c8e5a1d40f73"
down_revision: Union[str, Sequence[str], None] = "719a012becf1"
branch_labels = None
depends_on = None

TEAM_EMAILS = (
    "14aarush9@gmail.com",
    "aniketkumarshawtech@gmail.com",
    "aaryakapoor14@gmail.com",
    "aarya.goxl@gmail.com",
    "ayushray2403@gmail.com",
    "ayushkumar20060324@gmail.com",
    "ayushgoxl@gmail.com",
    "ayush2403kumar@gmail.com",
    "d.viraj2@gmail.com",
    "goxloffice@gmail.com",
    "goxlmarketing@gmail.com",
    "goxl.work@gmail.com",
    "godblesspower7@gmail.com",
    "pranjalsavantsavant@gmail.com",
    "pranjalmaheshsavant@gmail.com",
    "info@goxl.in",
    "sumitgoxlofficial@gmail.com",
    "sumitsuman4411@gmail.com",
)


def upgrade() -> None:
    result = op.get_bind().execute(
        sa.text(
            """
            UPDATE public.founders
               SET plan_type = 'pro'
             WHERE lower(email) = ANY(:emails)
               AND coalesce(plan_type, '') <> 'pro'
            """
        ),
        {"emails": list(TEAM_EMAILS)},
    )
    # Printed, not asserted. Fewer rows than addresses is the NORMAL case --
    # someone on the list has not registered yet, or is already pro -- so a
    # count check here would fail a deploy over a perfectly healthy state.
    print(f"[team-access] held {result.rowcount} account(s) at pro "
          f"out of {len(TEAM_EMAILS)} listed")


def downgrade() -> None:
    """Deliberately empty -- see the module docstring."""
