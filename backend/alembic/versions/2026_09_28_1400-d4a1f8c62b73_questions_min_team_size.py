"""questions: record the smallest team that can answer a question, and finish
the Team & Leadership half of the `problems.dimension_code` backfill.

THE DEFECT. `founders.team_size` was never asked for (until the onboarding
question added on 2026-09-28), so the diagnosis had no way to know how many
people work anywhere, and nothing in the question bank said which questions
need other people to exist. A founder working alone was therefore walked
through "Can your staff agree a discount without asking you?" and "When you
last hired, how did you check they could do the work?" -- and the blank or
apologetic answer that follows is scored as a gap in Team & Leadership rather
than as a question that should never have been asked.

WHY ON `questions` AND NOT ON `problems`. The opposite of the call migration
c3f7b28d5e91 made for `dimension_code`, and for a reason visible in the live
text: team-dependence varies WITHIN a problem, pillar and dimension does not.
Under the single problem `Unclear Decision Rights`, the two Stage 0 questions
for agritech are

    S0-AGR-205-1  Can anyone besides you agree a price with a farmer or buyer?
    S0-AGR-205-2  Do you know the lowest price you can accept and still make
                  money?

The first is unanswerable with nobody else in the business. The second is a
question about what the founder knows, and a solo founder answers it as well as
anyone. That pattern repeats across the bank -- `-1` asks whether somebody else
may act, `-2` asks whether a rule is written down or what something costs. The
sharpest case is the problem literally named `Solo Founder or Lack of
Co-founders`, whose questions run from "Have you worked together on a project
before?" (needs a co-founder) to "Do you believe, deep down, that nobody else
would care about this idea as much as you do?" (written for someone with none).
A problem-level column could not tell those apart, so the unit has to be the
question -- which is also the unit actually served to a founder.

THE SAFE DEFAULT, STATED RATHER THAN GUESSED. Every question under a pillar 5
problem is set to '2_5' here. That is a policy, not an inference: Team &
Leadership's three Business DNA dimensions are Decision Rights, Hiring
Repeatability and Team Structure & Role Clarity, and all three presuppose
people other than the founder. So a Team & Leadership question needs a team
until a human has read it and said otherwise, and the content pass OPENS UP the
solo-answerable ones rather than having to find and close the team-only ones.
Getting the default the other way round is what produced the defect.

A keyword rule was tried for the backfill and is deliberately NOT used. Matched
against the real text it is wrong in both directions: "If you hired someone next
month, what would you write down as the role?" mentions hiring and is perfectly
answerable alone, while "Does everyone know which part of the game is theirs?"
and "Which decisions still come to you that should not?" mention nobody and
cannot be answered without a team. Only the reviewed list below is trusted.

WHAT IS REVIEWED HERE. `_SOLO` is every Stage 0 pillar 5 question read
individually and judged answerable by someone working alone -- 45 of the 210.
Stage 0 first because that is where a founder with no team overwhelmingly is.
The other two stage groups stay at the '2_5' default and are the content pass's
work; `scripts/backfill_problem_dimensions.py --report` is the model for the
worksheet. Three judgements worth recording, because they are the ones a
reviewer will want to argue with:

  * "Do you write the job down before hiring?" stays at '2_5', for every
    industry. It asks about a hiring practice, and a founder who has never
    hired and is not hiring has nothing to describe -- the diagnosis would read
    that blank as a gap. Kept consistent across the whole family rather than
    split on whether the wording says "before hiring" or "before you look".
  * "Do you keep any record of which freelancers delivered well?" stays at
    '2_5'. Onboarding counts long-term freelancers as team, so a founder who
    answers 'solo' there is saying they have none.
  * "Who handles a customer dispute?" and the "Do people know which stage is
    theirs?" family stay at '2_5'. A solo founder can answer "me", but the
    question is put as though work is divided, and the reports read the answer
    that way.

NOTHING READS THE COLUMN YET. This migration only records the fact. The
candidate-question filter that acts on it is a separate change, so this can be
deployed, inspected and corrected before it changes what any founder is asked.

DIMENSION_CODE. c3f7b28d5e91 left Team & Leadership unassigned on purpose --
"several categories span three of their pillar's dimensions at once, so
assigning one would be fake precision... those need the live problem names and
subcategories, which this migration deliberately does not guess at". Those names
are now in hand, so the second half of this migration assigns them, by
subcategory where a subcategory is single-valued and by problem name where it is
not. Seven groups are left NULL on purpose and the reasons are recorded beside
them; NULL still means "not yet known", never "out of scope".

Revision ID: d4a1f8c62b73
Revises: e7c2a94f1b58
Create Date: 2026-09-28 14:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d4a1f8c62b73"
down_revision: Union[str, Sequence[str], None] = "e7c2a94f1b58"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_COLUMN = "min_team_size"
_CONSTRAINT = "questions_min_team_size_check"
_INDEX = "idx_questions_min_team_size"

#: founders.team_size's six coded values, in order. Reused rather than
#: redeclared so a question can never require a size a founder cannot state;
#: mirrors founders_team_size_check and TeamSize in app/schemas/founder.py.
_TEAM_SIZES: tuple[str, ...] = ("solo", "2_5", "6_10", "11_25", "26_50", "50_plus")

#: Team & Leadership. Hard-coded rather than looked up by name because a
#: migration has to keep working when the pillar is renamed.
_TEAM_PILLAR_ID = 5

#: The 45 Stage 0 Team & Leadership questions that a founder working alone can
#: answer, each read individually. Grouped by what makes it answerable, because
#: the grouping is the argument.
_SOLO: tuple[str, ...] = (
    # Decision Rights, `-2` side: is a limit written down, and does the founder
    # know what the thing costs. Neither needs anyone else to exist.
    "S0-AGR-205-2", "S0-AUT-205-2", "S0-BFS-205-2", "S0-BPC-205-2",
    "S0-CEL-305-2", "S0-DLV-305-2", "S0-ECM-305-2", "S0-EDU-305-2",
    "S0-ENR-305-2", "S0-FSH-305-2", "S0-GAM-305-2", "S0-HLT-305-1",
    "S0-HRT-305-2", "S0-LGL-305-1", "S0-LOG-305-1", "S0-MED-305-2",
    "S0-MFG-305-2", "S0-NGO-305-2", "S0-PHM-305-1", "S0-PRP-205-2",
    "S0-RTL-305-2", "S0-SAS-305-1", "S0-SPF-305-2", "S0-TEL-305-2",
    "S0-TRD-305-1", "S0-TRV-305-2", "S0-TXT-305-2",
    # The founder's own standards and records: a repair standard, an
    # installation method, a readiness standard, where client details are kept.
    "S0-BPC-103-2", "S0-BPC-104-2", "S0-CEL-304-2", "S0-CEL-306-2",
    "S0-ECM-103-2", "S0-ENR-304-2", "S0-ENR-306-1", "S0-MED-304-2",
    "S0-RTL-304-2", "S0-TRV-304-2", "S0-TXT-304-2",
    # Forward-looking about a team the founder does not have yet -- and the
    # three written for a solo founder specifically.
    "S0-SAS-104-1", "S0-SAS-104-2",
    "TM-009", "TM-020", "TM-095", "TM-096", "TM-097",
)

#: Pillar 5's three Business DNA dimensions. Any other code would score under
#: one pillar and report under another, so upgrade() refuses one.
_TEAM_DIMENSIONS: tuple[str, ...] = (
    "decision_rights", "hiring_repeatability", "team_structure_role_clarity",
)

#: subcategory -> dimension, for the pillar 5 subcategories that are
#: single-valued. Follows the assignments already in the table: retention,
#: turnover, attrition and hiring capability are Hiring Repeatability;
#: ownership, escalation and who-decides are Decision Rights; consistency and
#: standards are Team Structure & Role Clarity.
_BY_SUBCATEGORY: dict[str, str] = {
    # Finding, testing, training and keeping people.
    "Hiring": "hiring_repeatability",
    "Team Quality": "hiring_repeatability",
    "Early-Stage Onboarding": "hiring_repeatability",
    "FoodTech Staffing": "hiring_repeatability",
    "Gaming Talent Retention": "hiring_repeatability",
    "HealthTech Clinical Capacity": "hiring_repeatability",
    "Legal Senior Talent": "hiring_repeatability",
    "Marketing Talent Retention": "hiring_repeatability",
    "Media Talent Risk": "hiring_repeatability",
    "Travel Staffing": "hiring_repeatability",
    # Who is responsible for what, and whether that survives contact with
    # growth. Performance tracking is here and not under hiring: it measures
    # someone against a role, which is what the dimension is about.
    "Early-Stage Performance Tracking": "team_structure_role_clarity",
    "Culture": "team_structure_role_clarity",
    "Team Structure": "team_structure_role_clarity",
    "Logistics Driver Dependency": "team_structure_role_clarity",
    "Manufacturing Skill Dependency": "team_structure_role_clarity",
    # Who has final say.
    "Co-founder Dynamics": "decision_rights",
    "Governance": "decision_rights",
}

#: `People Management Complexity` holds ten problems that split across all
#: three dimensions, so it is assigned by problem name instead.
_BY_PROBLEM_NAME: dict[str, str] = {
    "Leading Through Managers Instead of Directly": "decision_rights",
    "Internal Politics and Competing Interests": "decision_rights",
    "New Managers Not Equipped to Lead": "hiring_repeatability",
    "No Performance Management System": "team_structure_role_clarity",
    "Compensation and Equity Complexity": "team_structure_role_clarity",
    "Culture Failing to Scale Intentionally": "team_structure_role_clarity",
    "Employee Disconnection and Morale Decline": "team_structure_role_clarity",
    "Role Ambiguity and Unclear Career Paths": "team_structure_role_clarity",
    "No Organisational Health Monitoring": "team_structure_role_clarity",
}

#: Left NULL on purpose, with the reason. Printed by upgrade() so a later
#: reviewer sees these were considered rather than missed.
_DELIBERATELY_NULL: tuple[tuple[str, str], ...] = (
    ("HR Technology",
     "people tooling, like Marketing Execution's tooling problems -- no "
     "dimension among Part 2's twenty"),
    ("No Succession Planning or Key Person Risk",
     "key-person dependency is pillar 1's Founder Dependency; assigning a "
     "pillar 5 dimension would score it under the wrong pillar"),
    ("Services Founder Dependency", "founder dependency, pillar 1"),
    ("Legal Founder Capacity", "founder dependency, pillar 1"),
    ("Marketing Founder Capacity", "founder dependency, pillar 1"),
    ("NGO Founder Fundraising Dependency", "founder dependency, pillar 1"),
    ("SaaS Founder Led Sales", "founder dependency, pillar 1"),
)


def _values_sql(values: Sequence[str]) -> str:
    return ", ".join(f"'{v}'" for v in values)


def upgrade() -> None:
    bind = op.get_bind()

    # --- the column -------------------------------------------------------
    op.add_column("questions", sa.Column(_COLUMN, sa.String(20), nullable=True))
    op.create_check_constraint(
        _CONSTRAINT, "questions",
        f"{_COLUMN} IS NULL OR {_COLUMN} IN ({_values_sql(_TEAM_SIZES)})",
    )
    # The candidate query filters on this together with the stage group, and
    # the rows that carry a value are a minority of the table.
    op.create_index(
        _INDEX, "questions", [_COLUMN], postgresql_where=sa.text(f"{_COLUMN} IS NOT NULL"),
    )

    # --- the safe default for Team & Leadership ---------------------------
    defaulted = bind.execute(
        sa.text(
            f"""
            UPDATE questions q SET {_COLUMN} = '2_5'
            FROM problems p
            WHERE p.problem_id = q.problem_id
              AND p.pillar_id = :pillar
              AND q.{_COLUMN} IS NULL
            """
        ),
        {"pillar": _TEAM_PILLAR_ID},
    ).rowcount
    print(f"[{revision}] {defaulted} Team & Leadership questions default to '2_5'")

    # --- the reviewed solo list -------------------------------------------
    opened = bind.execute(
        sa.text(
            f"""
            UPDATE questions SET {_COLUMN} = 'solo'
            WHERE question_code = ANY(:codes)
            """
        ),
        {"codes": list(_SOLO)},
    ).rowcount
    print(f"[{revision}] {opened} of {len(_SOLO)} reviewed questions opened to 'solo'")
    if opened != len(_SOLO):
        missing = bind.execute(
            sa.text(
                "SELECT c FROM unnest(CAST(:codes AS text[])) AS c "
                "WHERE c NOT IN (SELECT question_code FROM questions)"
            ),
            {"codes": list(_SOLO)},
        ).scalars().all()
        # Not fatal: a database built from a different batch set legitimately
        # holds fewer questions. Silence would be the problem.
        print(f"[{revision}] WARNING not in this database: {sorted(missing)}")

    # A reviewed question that is not Team & Leadership would mean the list was
    # built against a different bank; the filter would then quietly widen some
    # other pillar.
    stray = bind.execute(
        sa.text(
            """
            SELECT q.question_code FROM questions q
            JOIN problems p ON p.problem_id = q.problem_id
            WHERE q.question_code = ANY(:codes) AND p.pillar_id <> :pillar
            """
        ),
        {"codes": list(_SOLO), "pillar": _TEAM_PILLAR_ID},
    ).scalars().all()
    if stray:
        raise RuntimeError(
            f"reviewed as solo but not Team & Leadership: {sorted(stray)}"
        )

    # --- dimension_code, the half c3f7b28d5e91 deferred -------------------
    by_sub = bind.execute(
        sa.text(
            """
            UPDATE problems SET dimension_code = v.dim
            FROM (SELECT * FROM unnest(CAST(:subs AS text[]), CAST(:dims AS text[]))
                  AS t(sub, dim)) v
            WHERE problems.pillar_id = :pillar
              AND problems.subcategory = v.sub
              AND problems.dimension_code IS NULL
            """
        ),
        {
            "subs": list(_BY_SUBCATEGORY),
            "dims": list(_BY_SUBCATEGORY.values()),
            "pillar": _TEAM_PILLAR_ID,
        },
    ).rowcount
    by_name = bind.execute(
        sa.text(
            """
            UPDATE problems SET dimension_code = v.dim
            FROM (SELECT * FROM unnest(CAST(:names AS text[]), CAST(:dims AS text[]))
                  AS t(name, dim)) v
            WHERE problems.pillar_id = :pillar
              AND problems.problem_name = v.name
              AND problems.dimension_code IS NULL
            """
        ),
        {
            "names": list(_BY_PROBLEM_NAME),
            "dims": list(_BY_PROBLEM_NAME.values()),
            "pillar": _TEAM_PILLAR_ID,
        },
    ).rowcount
    print(f"[{revision}] dimension_code set on {by_sub} problems by subcategory "
          f"and {by_name} by problem name")

    # Same invariant c3f7b28d5e91 checks: a dimension must sit in its
    # problem's pillar, because the Business Health Score attributes by pillar.
    bad = bind.execute(
        sa.text(
            """
            SELECT problem_id, problem_name, dimension_code FROM problems
            WHERE pillar_id = :pillar
              AND dimension_code IS NOT NULL
              AND dimension_code <> ALL(:dims)
            """
        ),
        {"pillar": _TEAM_PILLAR_ID, "dims": list(_TEAM_DIMENSIONS)},
    ).all()
    if bad:
        raise RuntimeError(f"pillar 5 problems carrying a non-pillar-5 dimension: {bad}")

    still_null = bind.execute(
        sa.text(
            "SELECT count(*) FROM problems "
            "WHERE pillar_id = :pillar AND dimension_code IS NULL"
        ),
        {"pillar": _TEAM_PILLAR_ID},
    ).scalar_one()
    print(f"[{revision}] {still_null} Team & Leadership problems remain unassigned; "
          f"{len(_DELIBERATELY_NULL)} groups are deliberate:")
    for name, why in _DELIBERATELY_NULL:
        print(f"[{revision}]   {name}: {why}")


def downgrade() -> None:
    bind = op.get_bind()

    # Revert only the dimension codes this migration is responsible for. A
    # blanket clear would also wipe what c3f7b28d5e91 and the question batches
    # assigned.
    bind.execute(
        sa.text(
            """
            UPDATE problems SET dimension_code = NULL
            WHERE pillar_id = :pillar
              AND (subcategory = ANY(:subs) OR problem_name = ANY(:names))
            """
        ),
        {
            "pillar": _TEAM_PILLAR_ID,
            "subs": list(_BY_SUBCATEGORY),
            "names": list(_BY_PROBLEM_NAME),
        },
    )

    op.drop_index(_INDEX, table_name="questions")
    op.drop_constraint(_CONSTRAINT, "questions", type_="check")
    op.drop_column("questions", _COLUMN)
