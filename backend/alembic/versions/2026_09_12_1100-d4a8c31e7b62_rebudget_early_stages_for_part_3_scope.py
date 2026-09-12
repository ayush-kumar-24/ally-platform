"""Re-budget the three early stages for the Part 3 pillar scope

`8f3a1c92d7b4` set the per-stage question budgets, and set them against the
scope table as it stood: "They track how many readiness pillars each stage is
diagnosed on (see app/api/v1/diagnosis/stage_scope.py). Ideation is scoped to
two pillars, so thirty questions would mean re-asking the same two subjects
fifteen times each; fourteen covers them without padding."

That premise no longer holds. `b358e0b` rewrote the scope table to match
GoXL_Business_DNA Part 3, which widened all three early stages:

    stage_order            pillars was  now   budget was  answers/pillar
    1 Ideation                       2    4           14             3.5
    2 Validation                     3    6           20             3.3
    3 Prototype / MVP                4    6           24             4.0
    4 Early Traction                 6    6           30             5.0

The budget is the completion ceiling AND the coverage denominator
(`Settings.question_budget`), so leaving it alone did not shorten anything --
it spread the same number of questions over half as many subjects again. Every
stage from Early Traction on gets 5 answers per pillar; the three below it were
getting 3 to 4, and a pillar's answer count is the resolution of its score.

This restores 5 answers per pillar across the board:

    1 Ideation          14 -> 20    (4 pillars)
    2 Validation        20 -> 30    (6 pillars)
    3 Prototype / MVP   24 -> 30    (6 pillars)

Stages 4-8 are untouched -- they were already sized for six pillars.

WHY 2, 3 AND 4 NOW MATCH. Part 3 treats Validation, Prototype and Early
Traction as ONE band on one dimension set. One band, one scope, one budget is
the consistent reading; the old ladder between them encoded a pillar difference
that Part 3 does not make.

WHY THIS MATTERS BEYOND TIDINESS. It is what makes the ideation Business Health
Score trustworthy enough to publish, which the same commit as this migration
turns on. At 14 questions over four pillars a founder who abandoned two would
leave a pillar on two answers, and a two-answer pillar can only land on five
values while the founder is shown a BAND. Twenty gives four pillars five answers
each, clear of MIN_ANSWERS_PER_PILLAR_SCORE with room for a founder who drops
some.

FLOORS STILL CLEARED. `CONFIDENCE_MIN_QUESTIONS_FLOOR` is 12 and
`MIN_ANSWERS_BEFORE_COMPLETION` is 8; the smallest budget here is 20.

ONLY WHERE UNTOUCHED SINCE THE SEED. `8f3a1c92d7b4` set these values and said
the column exists to be hand-edited in production without a deploy. So this
updates a row only if it still holds that migration's exact number. A row
somebody has since tuned is left alone and reported, because overwriting a
deliberate production value is worse than leaving a stale one.

Revision ID: d4a8c31e7b62
Revises: c3f7b28d5e91
Create Date: 2026-09-12 11:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d4a8c31e7b62"
down_revision: Union[str, Sequence[str], None] = "c3f7b28d5e91"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

#: stage_order -> (budget set by 8f3a1c92d7b4, budget for the Part 3 scope)
_REBUDGET: dict[int, tuple[int, int]] = {
    1: (14, 20),
    2: (20, 30),
    3: (24, 30),
}


def upgrade() -> None:
    _apply({order: (was, now) for order, (was, now) in _REBUDGET.items()})


def downgrade() -> None:
    _apply({order: (now, was) for order, (was, now) in _REBUDGET.items()})


def _apply(moves: dict[int, tuple[int, int]]) -> None:
    """Move each stage's budget from `expected` to `target`, skipping any row
    that does not currently hold `expected`."""
    bind = op.get_bind()
    for stage_order, (expected, target) in sorted(moves.items()):
        current = bind.execute(
            sa.text(
                "SELECT question_budget FROM public.founder_stages "
                "WHERE stage_order = :o"
            ),
            {"o": stage_order},
        ).scalar()

        if current is None:
            # Never seeded on this environment. Setting it here would apply a
            # budget 8f3a1c92d7b4 deliberately left for its own run to decide.
            print(
                f"  [{revision}] stage_order {stage_order}: question_budget is "
                "NULL (unseeded); left alone."
            )
            continue

        if int(current) == target:
            # Already there -- a replay, or an environment somebody moved by
            # hand first. Nothing to say beyond that it is correct; reporting it
            # as an untouched local value would read like a warning.
            print(
                f"  [{revision}] stage_order {stage_order}: question_budget is "
                f"already {target}."
            )
            continue

        if int(current) != expected:
            print(
                f"  [{revision}] stage_order {stage_order}: question_budget is "
                f"{int(current)}, not the seeded {expected} -- left alone as a "
                f"deliberate local value. Part 3 scope wants about {target}."
            )
            continue

        bind.execute(
            sa.text(
                "UPDATE public.founder_stages SET question_budget = :b "
                "WHERE stage_order = :o"
            ),
            {"b": target, "o": stage_order},
        )
        print(
            f"  [{revision}] stage_order {stage_order}: question_budget "
            f"{expected} -> {target}"
        )
