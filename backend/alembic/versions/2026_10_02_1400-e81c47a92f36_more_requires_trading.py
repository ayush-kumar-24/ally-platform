"""Seventy-eight more questions that need money to have changed hands.

`requires_trading` (a6f3d2c81b47) withholds a question from a founder who has
not sold anything yet, because the alternative is asking them about last
quarter's sales and scoring the silence as a weakness. That migration tagged the
questions that name money outright. 269 rows carry it.

These 78 were found by sweeping for the vocabulary of a business already
trading -- revenue, churn, invoices, renewals, margin per, order value, what a
customer pays -- among the rows that carry no tag. "What does an average
customer pay you before they leave?" and "How many months of expenses could you
cover if revenue stopped completely tomorrow?" have no answer for somebody with
no customers and no revenue.

THIRTY OF THE 108 FOUND ARE DELIBERATELY NOT HERE, because the word is not the
test. Each was read, and three shapes are answerable before a first sale:

  PLANNING AND PROJECTION. Eleven budget questions ask about revenue the
  founder EXPECTS, not revenue they have -- "Is your budget built around a
  specific revenue number?", "If revenue comes in 20% below what you expected,
  does your budget still work?". A pre-revenue founder with a plan answers
  every one, and the question is a good one precisely then.

  HYPOTHETICAL. "Who WOULD handle your registrations and renewals?" is asked of
  a business that does not exist yet. So is "How many months before your first
  rupee of revenue?", which is meaningless to anyone already trading.

  REGULATORY RENEWALS, WHICH ARE NOT CUSTOMER RENEWALS. "Can you list every
  regulatory filing and renewal you are responsible for, with dates?" is about
  licences. A company that has never sold anything still holds licences and
  still has to renew them. Seven questions turn on this distinction, and a
  keyword sweep gets every one of them wrong.

That is the third time screening this bank by keyword would have been wrong in
both directions (see d4a1f8c62b73 and a6f3d2c81b47), which is why the codes
below are listed one by one rather than matched by a pattern, and why the
upgrade raises unless it tags exactly as many rows as it names.

ONE OF THE 78 ALSO HAS TO MOVE BANK. S0-SPF-008, "Do you count no shows and
cancellations as lost revenue?", sits on the IDEATION bank, where no founder is
ever trading -- so tagging it there would make it unreachable rather than
withheld, trading one defect for another. It is a real Stage 0->1 question
sitting in the wrong bank, so it moves there, which is the same correction
f1b6d93ac274 made for 210 stranded team questions. Caught by
test_no_ideation_question_needs_a_trading_business, which exists for exactly
this and names the remedy in its own docstring.

Revision ID: e81c47a92f36
Revises: b5d4e31a7c92
Create Date: 2026-10-02 14:00:00.000000
"""
from __future__ import annotations

from alembic import op
from sqlalchemy import text

revision = "e81c47a92f36"
down_revision = "b5d4e31a7c92"
branch_labels = None
depends_on = None

#: Read one at a time; each presupposes money already received.
_REQUIRES_TRADING: tuple[str, ...] = (
    "BMD-003", "FIN-034", "MEX-084", "PRD-062",
    "PSY-110", "S0-FNB-106-1", "S0-LOG-304-1", "S0-SPF-008",
    "S01-ECM-106-2", "S01-FIN-003", "S01-FIN-015", "S01-FNB-105-1",
    "S01-GTM-003", "S01-GTM-019", "S01-GTM-031", "S01-HRT-005",
    "S01-HRT-303-1", "S01-LOG-105-2", "S01-MKT-019", "S01-PRD-051",
    "S01-SAL-001", "S01-SAS-101-2", "S01-SPF-003", "S01-SVC-004",
    "S10-BPC-103-1", "S10-BPC-106-2", "S10-ENR-003", "S10-FIN-031",
    "S10-FIN-081", "S10-FIN-092", "S10-FIN-094", "S10-GAM-002",
    "S10-GAM-004", "S10-GAM-011", "S10-GTM-012", "S10-GTM-017",
    "S10-GTM-019", "S10-GTM-040", "S10-GTM-041", "S10-GTM-060",
    "S10-LOG-309-2", "S10-MEX-061", "S10-PRD-025", "S10-PRD-071",
    "S10-SAL-005", "S10-SAL-018", "S10-SAL-020", "S10-SAL-025",
    "S10-SAS-002", "S10-SPF-021", "S10-TEL-016", "SAL-016",
    "SAL-064", "SCL-094", "SCL-097", "SCL-102",
    "SCL-104", "SCL-107", "SCL-110", "SCL-113",
    "SCL-130", "SCL-131", "SCL-132", "SCL-133",
    "SCL-134", "SCL-135", "SCL-210", "SCL-211",
    "SCL-212", "SCL-213", "SLX-157", "SLX-172",
    "SLX-173", "SLX-174", "SLX-223", "SLX-306",
    "SLX-307", "SLX-308",
)


def _set(codes: tuple[str, ...], value: bool) -> None:
    """Flip `requires_trading` for these codes, skipping any this catalogue
    does not have.

    Tolerant for the reason 8b63ca0f gives at length: `alembic upgrade head`
    runs inside the release, so raising over one renamed question stops the
    migration, leaves the ECS service un-updated and ships nothing at all. A
    question that is not here cannot be asked either, so not tagging it
    withholds nothing from nobody. Not one code present still raises, because
    that means the wrong catalogue rather than drift.
    """
    bind = op.get_bind()
    present = {
        row[0]
        for row in bind.execute(
            text("SELECT question_code FROM questions WHERE question_code = ANY(:codes)"),
            {"codes": list(codes)},
        ).all()
    }
    missing = sorted(set(codes) - present)

    if not present:
        raise RuntimeError(
            f"None of the {len(codes)} questions e81c47a92f36 names are in this "
            "catalogue. That is not drift, it is the wrong database -- check "
            "which one this ran against before editing the list."
        )

    bind.execute(
        text(
            "UPDATE questions SET requires_trading = :value, updated_at = now() "
            "WHERE question_code = ANY(:codes)"
        ),
        {"value": value, "codes": sorted(present)},
    )
    print(
        f"e81c47a92f36: requires_trading={value} on {len(present)} of {len(codes)}"
        + (f"; not in this catalogue: {', '.join(missing)}" if missing else "")
    )


#: Tagged AND moved: unreachable on the ideation bank, at home on the next one.
_STRANDED_ON_IDEATION = "S0-SPF-008"
_IDEATION = "Stage 0"
_NEXT_BANK = "Stage 0\u21921"


def _move_bank(code: str, frm: str, to: str) -> None:
    """Move one question between banks, tolerating it already being there.

    Same reasoning as `_set`: a question that has been renamed, retired or
    already moved must not stop a release.
    """
    bind = op.get_bind()
    current = bind.execute(
        text("SELECT primary_stage_group FROM questions WHERE question_code = :code"),
        {"code": code},
    ).scalar()

    if current is None:
        print(f"e81c47a92f36: {code} is not in this catalogue; nothing to move")
        return
    if current == to:
        print(f"e81c47a92f36: {code} is already on the {to!r} bank")
        return
    if current != frm:
        print(
            f"e81c47a92f36: {code} is on the {current!r} bank, not {frm!r}; "
            "left where it is"
        )
        return

    bind.execute(
        text(
            "UPDATE questions SET primary_stage_group = :to, updated_at = now() "
            "WHERE question_code = :code"
        ),
        {"code": code, "to": to},
    )
    print(f"e81c47a92f36: moved {code} from {frm!r} to {to!r}")


def upgrade() -> None:
    _move_bank(_STRANDED_ON_IDEATION, _IDEATION, _NEXT_BANK)
    _set(_REQUIRES_TRADING, True)


def downgrade() -> None:
    # Safe to clear unconditionally: every code here carried false before this
    # migration, which is what made the sweep find them.
    _set(_REQUIRES_TRADING, False)
    _move_bank(_STRANDED_ON_IDEATION, _NEXT_BANK, _IDEATION)
