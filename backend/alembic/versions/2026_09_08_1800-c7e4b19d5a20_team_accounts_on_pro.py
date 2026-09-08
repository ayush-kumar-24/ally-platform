"""The team's own accounts on Pro, so public launch does not lock them out.

PUBLIC_LAUNCH empties the Free tier: Free stops being a plan anyone holds and
becomes the state a founder is in before they have chosen one. Every account
still carrying `plan_type = 'free'` at that moment loses the product at once --
and with checkout unwired there is no self-serve way back. That includes the
people who build and test Ally, whose accounts were all created before there
were paid tiers to be on.

PUBLIC-LAUNCH-CHECKLIST.md calls this out as "the step that will hurt if it is
missed" and gives it as SQL for a human to run. It is a migration instead
because the flip ships through the same pipeline: a manual step that has to
happen in the window between a deploy going out and founders noticing is a step
that gets missed, and this one is missed silently -- a tester simply finds the
product gone.

WHY 'pro' AND NOT A NEW TIER
Pro is the whole feature set (`_BASE | _WORKSPACE | _ADVISOR` in plans/catalog).
An "internal" or "staff" tier would be a fourth thing to keep in step with the
catalog, the CHECK constraint and every gate, to describe a product nobody is
sold. The team gets the product a paying founder gets, which is also the only
version worth testing.

WHY THE ADDRESSES ARE LISTED, NOT MATCHED
No `like '%@goxl%'`. A pattern quietly sweeps in anyone who later signs up with
a company address, and the entire point of this list is knowing exactly who has
been handed the full product for nothing. The same reasoning as the checklist's
SQL, for the same reason.

WHAT THIS DOES NOT DO
It sets the plan on accounts that exist when it runs. An address on this list
that has no `founders` row yet -- someone who has not signed in, or a teammate
added later -- is reported in the deploy log and left alone; there is no row to
update, and inventing one would create a founder record with no identity behind
it. Granting those is an approval in the panel plus a plan set by hand, and
adding a new teammate later means another migration like this one.
"""

from alembic import op
import sqlalchemy as sa

revision = "c7e4b19d5a20"
down_revision = "b8e3d5a91c47"
branch_labels = None
depends_on = None

#: The team. Lowercased, because addresses are stored as they were typed and a
#: capital letter must not decide whether someone keeps the product.
TEAM_EMAILS = [
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
]

_TARGET_TIER = "pro"


def upgrade() -> None:
    bind = op.get_bind()

    # Report before changing anything: the deploy log is the only place anyone
    # will look if a teammate says they lost access, and "which of these had no
    # account" is the question that will be asked.
    found = bind.execute(
        sa.text("SELECT lower(email) FROM founders WHERE lower(email) IN :emails")
        .bindparams(sa.bindparam("emails", expanding=True)),
        {"emails": TEAM_EMAILS},
    ).scalars().all()

    missing = sorted(set(TEAM_EMAILS) - set(found))
    if missing:
        print(f"[team-accounts] no founders row, left alone: {', '.join(missing)}")

    result = bind.execute(
        sa.text(
            """
            UPDATE founders
               SET plan_type = :tier
             WHERE lower(email) IN :emails
               AND plan_type IS DISTINCT FROM :tier
            """
        ).bindparams(sa.bindparam("emails", expanding=True)),
        {"emails": TEAM_EMAILS, "tier": _TARGET_TIER},
    )

    print(
        f"[team-accounts] {result.rowcount} of {len(found)} existing team "
        f"accounts moved to '{_TARGET_TIER}' "
        f"({len(found) - result.rowcount} already there)"
    )


def downgrade() -> None:
    """Deliberately nothing.

    The reverse of this is not "put them back on free" -- that is the outage this
    migration exists to prevent, and it would land on the team the moment anyone
    stepped one revision back. Nor can it be "restore what they had before":
    every one of these was on `free` because there was nothing else to be on, so
    restoring it is the same harm by a longer route.

    Taking the grant away is a business decision, made per account, not a
    schema rollback.
    """
