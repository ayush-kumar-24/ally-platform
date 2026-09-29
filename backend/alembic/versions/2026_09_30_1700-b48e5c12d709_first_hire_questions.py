"""Twenty questions for a founder who has not hired anyone yet.

A founder working alone now gets the Team & Leadership questions they can
answer -- but at Validation, Prototype/MVP and Early Traction that is only
FIFTEEN, and every one is about founder dependency: is anyone checking your
thinking, is growth capped by what you can carry. All true, all worth asking,
and none of it about the thing a solo founder at that stage actually needs help
with -- when to hire, what to hand over first, and whether they can afford it.

Nothing in the catalogue asked that. The closest were two questions that allow
for not having hired ("Think about your first hire, or the person you'd hire
first if you haven't yet"), and both sat behind a team requirement.

TEAM STRUCTURE & ROLE CLARITY, NOT HIRING REPEATABILITY, and the reason is not
only semantic. Before a first hire there is no hiring process to make
repeatable; what exists is a role to define and work to hand over, which is
what Role Clarity means. And practically: Part 3 switches Hiring Repeatability
OFF at these three stages, so questions filed there would never reach the
founders these were written for.

TAGGED 'solo', which in this system means "anyone, including a founder working
alone" rather than "only them". A founder with two or three people will see
these too, which is deliberate -- "What would you hand over first?" and "Is
there work you keep meaning to hand over but never do?" are real questions at
three people. Showing them ONLY to founders with nobody would need a maximum
team size, which does not exist and is not worth inventing for twenty
questions.

Source: docs/drafts/first-hire-questions.md.

Revision ID: b48e5c12d709
Revises: c17a940e6b23
Create Date: 2026-09-30 17:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b48e5c12d709"
down_revision: Union[str, Sequence[str], None] = "c17a940e6b23"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_PROBLEM_CODE = "TML-FH1"
_ROOT_CAUSE_CODE = "RC-TML-FH1"
_GROUP = "Stage 0\u21921"
_PILLAR = 5
_CATEGORY = "Team & Leadership"
_DIMENSION = "team_structure_role_clarity"

#: None needs a sale to have happened, and all are answerable with nobody else
#: in the business -- that is the whole point of them.
_QUESTIONS: tuple[tuple[str, str], ...] = (
    ("FHIRE-01", 'What is the first thing you would hand to someone else if you hired tomorrow?'),
    ("FHIRE-02", 'What work are you doing today that you know is not worth your time?'),
    ("FHIRE-03", 'Do you know what you would pay someone, and can the business afford it?'),
    ("FHIRE-04", 'What would have to be true before you felt ready to hire?'),
    ("FHIRE-05", 'If you hired the wrong person, how long would it take you to notice?'),
    ("FHIRE-06", 'Have you written down what the job would actually involve?'),
    ("FHIRE-07", 'What stops you hiring right now — money, time, or something else?'),
    ("FHIRE-08", 'Is there work you keep meaning to hand over but never do?'),
    ("FHIRE-09", 'Would you know how to tell a good candidate from a confident one?'),
    ("FHIRE-10", 'How many hours a week would a first hire need to save you to be worth it?'),
    ("FHIRE-11", 'Do you believe nobody else could do this work to your standard?'),
    ("FHIRE-12", 'Who would you ask for advice before making your first hire?'),
    ("FHIRE-13", 'Would you start someone on a small piece of work first, or hire straight away?'),
    ("FHIRE-14", 'What would you need to write down before someone could start?'),
    ("FHIRE-15", 'Is there a part of the work you would never hand over, and why?'),
    ("FHIRE-16", 'Have you ever managed anyone before, in any job?'),
    ("FHIRE-17", 'What would break if you took someone on and they left after a month?'),
    ("FHIRE-18", 'Would you hire someone like you, or someone who fills your gaps?'),
    ("FHIRE-19", 'Is waiting to hire a money decision, or does it feel like losing control?'),
    ("FHIRE-20", 'If you hired someone next month, what would you want them doing by month three?'),
)


def upgrade() -> None:
    bind = op.get_bind()

    problem_id = bind.execute(
        sa.text(
            """
            INSERT INTO problems (problem_code, problem_name, category, layer,
                                  description, severity_min, severity_max,
                                  pillar_id, subcategory, dimension_code)
            VALUES (:code, 'Putting Off the First Hire', :category, 'internal',
                    'The founder is still doing work somebody else should be '
                    'doing, and has not decided what the first role would be.',
                    4, 8, :pillar, 'Before the First Hire', :dimension)
            ON CONFLICT (problem_code) DO NOTHING
            RETURNING problem_id
            """
        ),
        {"code": _PROBLEM_CODE, "category": _CATEGORY, "pillar": _PILLAR,
          "dimension": _DIMENSION},
    ).scalar()
    if problem_id is None:
        problem_id = bind.execute(
            sa.text("SELECT problem_id FROM problems WHERE problem_code = :c"),
            {"c": _PROBLEM_CODE},
        ).scalar_one()

    root_cause_id = bind.execute(
        sa.text(
            """
            INSERT INTO root_causes (root_cause_code, problem_id, root_cause_name,
                                     root_cause_category, explanation,
                                     confidence_weight, layer)
            VALUES (:code, :pid, 'Putting Off the First Hire', 'Operational',
                    'The work that should be handed over has not been named, '
                    'so there is nothing concrete to hire for.', 0.70, 'internal')
            ON CONFLICT (root_cause_code) DO NOTHING
            RETURNING root_cause_id
            """
        ),
        {"code": _ROOT_CAUSE_CODE, "pid": problem_id},
    ).scalar()
    if root_cause_id is None:
        root_cause_id = bind.execute(
            sa.text("SELECT root_cause_id FROM root_causes WHERE root_cause_code = :c"),
            {"c": _ROOT_CAUSE_CODE},
        ).scalar_one()

    added = 0
    for code, text in _QUESTIONS:
        added += bind.execute(
            sa.text(
                """
                INSERT INTO questions (question_code, category, question_text,
                                       problem_id, root_cause_id, question_type,
                                       difficulty_level, priority,
                                       primary_stage_group, min_team_size,
                                       requires_trading)
                VALUES (:code, :category, :text, :pid, :rid, 'open_text', 2,
                        'CORE', :group, 'solo', false)
                ON CONFLICT (question_code) DO NOTHING
                """
            ),
            {"code": code, "category": _CATEGORY, "text": text, "pid": problem_id,
              "rid": root_cause_id, "group": _GROUP},
        ).rowcount
    print(f"[{revision}] {added} of {len(_QUESTIONS)} first-hire questions added")

    solo = bind.execute(
        sa.text(
            """
            SELECT count(*) FROM questions q JOIN problems p
              ON p.problem_id = q.problem_id
            WHERE p.pillar_id = :pillar AND q.primary_stage_group = :group
              AND q.min_team_size = 'solo'
            """
        ),
        {"pillar": _PILLAR, "group": _GROUP},
    ).scalar_one()
    print(f"[{revision}] a founder working alone now has {solo} Team & "
          "Leadership questions before Growth")


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text("DELETE FROM questions WHERE question_code = ANY(:c)"),
                 {"c": [c for c, _t in _QUESTIONS]})
    bind.execute(sa.text("DELETE FROM root_causes WHERE root_cause_code = :c"),
                 {"c": _ROOT_CAUSE_CODE})
    bind.execute(sa.text("DELETE FROM problems WHERE problem_code = :c"),
                 {"c": _PROBLEM_CODE})
