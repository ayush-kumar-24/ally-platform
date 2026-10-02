"""Two expansion questions presume the founder has already entered a market.

Found in the stage-by-stage audit. Both sit in the Property bank at Growth /
Expansion / Maturity, and both are written as though expansion has already
happened:

    Do you have a local legal partner in each new market you've entered?
    Have you checked how stamp duty and registration costs differ in your new
    market?

A founder at Growth may be scaling in one city and have entered nothing. They
answer neither, and the diagnosis scores the silence -- the same defect
`min_team_size` and `requires_trading` exist for, on an axis with only two
questions behind it.

MADE CONDITIONAL RATHER THAN GATED, because a gate would need a fact nobody
collects -- how many markets the founder operates in -- and two questions do not
justify a fifth onboarding field. The conditional form costs nothing and reads
the same to a founder who HAS expanded, while a founder who has not can now
answer "not yet", which is itself the useful answer: both questions are really
asking whether the groundwork is in place before the move, and that is worth
knowing before it happens rather than after.

Note this is the opposite call from b5d4e31a7c92, which refused to reword 76
questions and withheld them instead. The difference is what the rewording costs:
there, the industry's own vocabulary was the specificity and removing it
flattened the question. Here, "you've entered" carries no information that "are
you entering" does not.

Revision ID: d6a93f15b802
Revises: e81c47a92f36
Create Date: 2026-10-02 14:30:00.000000
"""
from __future__ import annotations

from alembic import op
from sqlalchemy import bindparam, text

revision = "d6a93f15b802"
down_revision = "e81c47a92f36"
branch_labels = None
depends_on = None

_REWORD: tuple[tuple[str, str, str], ...] = (
    (
        "S10-PRP-003",
        "Do you have a local legal partner in each new market you've entered?",
        "For any new market you have entered or are planning to enter, do you "
        "have a local legal partner there?",
    ),
    (
        "S10-PRP-004",
        "Have you checked how stamp duty and registration costs differ in your "
        "new market?",
        "For any new market you are entering or considering, have you checked "
        "how stamp duty and registration costs differ there?",
    ),
)


def _apply(pairs: tuple[tuple[str, str, str], ...]) -> None:
    """Rewrite each question, skipping any whose text has moved on.

    Tolerant for the reason 8b63ca0f gives at length: a rewording that matches
    nothing because somebody already improved that question is not a failure --
    mine is the stale text and theirs should stand -- and raising inside
    `alembic upgrade head` stops the whole release rather than one rewording.
    Only a total mismatch, meaning the wrong catalogue, still raises.
    """
    stmt = text(
        """
        UPDATE questions SET question_text = :new, updated_at = now()
        WHERE question_code = :code AND question_text = :old
        """
    ).bindparams(bindparam("new"), bindparam("code"), bindparam("old"))

    bind = op.get_bind()
    applied = already_done = 0
    left_alone: list[str] = []

    for code, old, new in pairs:
        current = bind.execute(
            text("SELECT question_text FROM questions WHERE question_code = :code"),
            {"code": code},
        ).scalar()
        if current is None:
            left_alone.append(f"{code} (not in this catalogue)")
        elif current == new:
            already_done += 1
        elif current == old:
            bind.execute(stmt, {"code": code, "old": old, "new": new})
            applied += 1
        else:
            left_alone.append(f"{code} (text has moved on)")

    if applied == 0 and already_done == 0:
        raise RuntimeError(
            f"Neither of the questions named by {revision} was found with its "
            "expected text or its rewording. That is not drift, it is the wrong "
            f"catalogue. Left alone: {left_alone}"
        )

    print(
        f"{revision}: reworded {applied}, already done {already_done}, "
        f"left alone {len(left_alone)}"
        + (f" -- {'; '.join(left_alone)}" if left_alone else "")
    )


def upgrade() -> None:
    _apply(_REWORD)


def downgrade() -> None:
    _apply(tuple((code, new, old) for code, old, new in _REWORD))
