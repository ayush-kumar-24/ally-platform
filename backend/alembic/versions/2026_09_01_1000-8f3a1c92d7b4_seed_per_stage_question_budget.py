"""Seed the per-stage diagnosis question budget.

`c6a4e83f19d7` added `founder_stages.question_budget` and deliberately left
every row NULL, because what each stage's budget should be was a product
decision that had not been taken. It has now been taken, so this is the UPDATE
that migration described.

Until this runs, every stage falls back to `MAX_DIAGNOSIS_QUESTIONS` = 30, so a
founder with an idea and nothing built answers the same thirty questions as one
running a scaling company.

BUDGETS
-------
    1  Ideation           14
    2  Validation         20
    3  Prototype / MVP    24
    4  Early Traction     30
    5  Growth / Scaling   30
    6  Expansion          32
    7  Maturity           32
    8  Exit               30

They track how many readiness pillars each stage is diagnosed on (see
`app/api/v1/diagnosis/stage_scope.py`). Ideation is scoped to two pillars, so
thirty questions would mean re-asking the same two subjects fifteen times each;
fourteen covers them without padding. Expansion and Maturity get the most
because all six pillars are live AND the organisational subjects -- decision
rights, hiring repeatability, institutional memory -- carry the most weight
there.

WHY NOTHING IS BELOW 14
-----------------------
`CONFIDENCE_MIN_QUESTIONS_FLOOR` is 12: below twelve answers the confidence
score is capped and `generate_report` is unreachable, so a stage budgeted under
12 could never produce a report at all. `MIN_ANSWERS_BEFORE_COMPLETION` is 8.
Fourteen clears both with room for a founder who abandons one question.

This is data, not behaviour: the numbers are editable in production with an
UPDATE and no deploy, exactly as `c6a4e83f19d7` intended.

Revision ID: 8f3a1c92d7b4
Revises: ba7ca1acfa53
"""

from __future__ import annotations

from alembic import op

revision = "8f3a1c92d7b4"
down_revision = "ba7ca1acfa53"
branch_labels = None
depends_on = None

#: stage_order -> question budget.
_BUDGETS: dict[int, int] = {
    1: 14,
    2: 20,
    3: 24,
    4: 30,
    5: 30,
    6: 32,
    7: 32,
    8: 30,
}


def upgrade() -> None:
    # Keyed on stage_order rather than stage_id: order is the axis the scope
    # table and _STAGE_ORDER_TO_GROUP both read, and it survives a re-seed of
    # founder_stages that renumbers the ids.
    #
    # Only overwrite NULL. A non-null value is somebody's deliberate production
    # tuning of a column whose whole point is being hand-editable, and a replay
    # of this migration must not silently revert it.
    for stage_order, budget in _BUDGETS.items():
        op.execute(
            "UPDATE public.founder_stages "
            f"SET question_budget = {budget} "
            f"WHERE stage_order = {stage_order} AND question_budget IS NULL"
        )


def downgrade() -> None:
    # Back to NULL, which the reading code treats as "unset" and falls back to
    # MAX_DIAGNOSIS_QUESTIONS -- the state c6a4e83f19d7 shipped.
    order_list = ", ".join(str(o) for o in _BUDGETS)
    op.execute(
        "UPDATE public.founder_stages SET question_budget = NULL "
        f"WHERE stage_order IN ({order_list})"
    )
