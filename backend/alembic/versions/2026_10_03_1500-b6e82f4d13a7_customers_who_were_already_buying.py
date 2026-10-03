"""Thirteen more questions that presume customers who were already buying.

Found in test cases D3/D4/D5, running a pre-revenue founder at Prototype and at
Growth. Three were still reachable in their candidate pool:

    Do you know exactly which customers owe you money right now, and how
    overdue each payment is?
    Have any customers cancelled or stopped buying from you?
    If a big customer suddenly stopped buying, would you know within a day how
    that changes your runway?

Nobody has stopped buying from a founder nobody has started buying from.
Sweeping for that shape -- money owed, customers lost, a biggest customer --
found ten more.

HALF THE SWEEP WAS NOISE, which is why these are listed and not matched.
Twenty-six questions contain the pattern and thirteen are nothing to do with
it: "collection" means a fashion collection in six of them ("Does your next
collection of clothes match what your brand stands for?") and data collection
in four ("Is your data collection standardized?"). A regex cannot tell those
from "which customers owe you money", and this is the fifth time in this area
that it could not.

ONE LEFT ALONE DELIBERATELY. S10-SAS-023, "If a competitor copied your product,
what would stop customers leaving?", is a question about moat. A founder with no
customers yet can and should reason about it, and tagging it would withhold a
strategy question on the grounds that its illustration mentions customers.

Revision ID: b6e82f4d13a7
Revises: a95e3d17c284
Create Date: 2026-10-03 15:00:00.000000
"""
from __future__ import annotations

from alembic import op
from sqlalchemy import text

revision = "b6e82f4d13a7"
down_revision = "a95e3d17c284"
branch_labels = None
depends_on = None

#: Each presumes a customer who was already buying -- money owed, an account
#: lost, a biggest customer to lose. Read one at a time.
_REQUIRES_TRADING: tuple[str, ...] = (
    "FIN-032",        # which customers owe you money, and how overdue
    "SAL-022",        # have any customers cancelled or stopped buying
    "S01-FIN-009",    # if a big customer paid thirty days late
    "S01-SAS-011",    # how many customers cancelled in the last three months
    "S01-SPF-305-2",  # has a member cancelled while waiting for your answer
    "S10-FIN-082",    # if a big customer stopped buying, your runway
    "S10-MFG-002",    # who sets your price, you or your biggest customer
    "S10-PRD-063",    # if your biggest customer had an outage
    "S10-PRD-076",    # your newest largest vs your earliest customers
    "S10-SAL-029",    # if your largest customer asked for a discount to stay
    "S10-SAS-022",    # who sets the terms with your largest customer
    "S10-FSH-025",    # before a new collection, do you review what actually sold
    "S10-TRD-003",    # has a registration lapsed and blocked a shipment
)

_IDEATION = "Stage 0"


def _set(codes: tuple[str, ...], value: bool) -> None:
    """Flip `requires_trading`, skipping codes this catalogue does not have.

    Tolerant for the reason 8b63ca0f gives: raising inside `alembic upgrade
    head` stops the release, and a question that is not here cannot be asked
    either. Not one code present still raises -- wrong catalogue, not drift.

    Also refuses to strand a question on the ideation bank, where no founder is
    ever trading: a tag there makes it unreachable rather than withheld, which
    is the trap e81c47a92f36 hit with S0-SPF-008.
    """
    bind = op.get_bind()
    rows = bind.execute(
        text(
            "SELECT question_code, primary_stage_group FROM questions "
            "WHERE question_code = ANY(:codes)"
        ),
        {"codes": list(codes)},
    ).all()
    present = {r[0] for r in rows}
    missing = sorted(set(codes) - present)

    if not present:
        raise RuntimeError(
            f"None of the {len(codes)} questions {revision} names are in this "
            "catalogue. That is the wrong database, not drift."
        )

    if value:
        stranded = sorted(r[0] for r in rows if r[1] == _IDEATION)
        if stranded:
            raise RuntimeError(
                f"{stranded} would be tagged on the {_IDEATION!r} bank, where no "
                "founder is ever trading, so they would become unreachable "
                "rather than withheld."
            )

    bind.execute(
        text(
            "UPDATE questions SET requires_trading = :value, updated_at = now() "
            "WHERE question_code = ANY(:codes)"
        ),
        {"value": value, "codes": sorted(present)},
    )
    print(
        f"{revision}: requires_trading={value} on {len(present)} of {len(codes)}"
        + (f"; not in this catalogue: {', '.join(missing)}" if missing else "")
    )


def upgrade() -> None:
    _set(_REQUIRES_TRADING, True)


def downgrade() -> None:
    _set(_REQUIRES_TRADING, False)
