"""Stop asking idea-stage founders about a business they have not started.

THE DEFECT, reported from reading a live diagnosis: a founder whose idea exists
only in their head and on paper was asked

    OPS-004  How do you handle customer support or service requests?
    PRD-021  How many active users or customers do you currently have?
    PSY-002  How do you typically react when your startup hits a major setback?

They have no customers, no users and no startup. Same shape as the team-size
defect: the question presupposes something the founder does not have, they
answer nothing, and `business_health` scores the blank as a gap.

WHY STAGE SCOPE DID NOT CATCH IT. `stage_scope` withholds whole pillars,
categories and dimensions, and it works -- Revenue Maturity and Team &
Leadership are already off at ideation. But the presupposition varies WITHIN a
category, exactly as team-dependence varies within a problem. Under
`Product`, "What's the simplest version of this you could put in front of
someone today using only free or no-code tools?" is written for someone with
nothing built, and "Rate from 1 to 5 how well your product currently solves the
target problem" cannot be answered by them. A category filter takes both or
neither.

WHERE THE PROBLEM IS, AND WHERE IT IS NOT. 1,171 questions are reachable by an
ideation founder, and the split is clean along question_code:

    988  `S0-` prefixed, written for the Stage 0 bank on purpose. 267
         universal and all 721 industry-owned ones. These are sound -- they
         ask about a prototype, a test, a tool, an assumption, and several
         explicitly allow for nothing existing yet.
    183  legacy codes (PSY-, IVA-, TCI-, PRD-, OPS-, CMA-, BPL-, RSK-),
         written before the Stage 0 bank existed and tagged into it afterwards.

All 183 were read. Seventeen are wrong, and they are all legacy. The rest are
genuinely answerable by someone with an idea -- Founder Psychology especially,
which is about the person rather than the business and is the pillar ideation
leans on most.

THREE DIFFERENT FIXES, because the questions are wrong in three ways.

  RETAGGED to Stage 0->1 (10). The subject itself is not an ideation subject.
  Customer support, active user counts, a product roadmap, a maintenance plan,
  a deal falling through, an investor who funded a direction. No wording saves
  these; they belong to a business that is running.

  REWORDED (5). The subject IS valid at ideation and only the wording assumes
  a running business -- "your startup", "since starting the venture", "this
  business", "your company". How a founder handles a setback or what happened
  to their sleep matters as much before they start as after. Rewritten to say
  the same thing without the premise, and kept short and plain, which is the
  standing rule for question text.

  GATED ON TEAM SIZE (2). RSK-006 asks what "your team" would list as risks and
  IVA-060 asks whether "employees" have become attached to existing work. Both
  sit under pillars 6 and 2, so the Team & Leadership defaults set by
  d4a1f8c62b73 never reached them. They get `min_team_size = '2_5'` so
  `team_scope` withholds them from anyone working alone, at every stage -- this
  is not an ideation-only problem, a solo founder at Growth should not get them
  either.

NOT DONE HERE. The 183 legacy questions include the jargon this repository has
a standing rule against -- "structured problem validation methodology",
"white-space opportunities", "validation methodologies like Lean Startup or
Design Thinking". Rewriting for plainness is a separate pass over the whole
bank (799 questions run past 110 characters) and is not mixed into a correctness
fix, so that the two can be reviewed and reverted independently.

Revision ID: c58d1e7b0a94
Revises: a2e7c481f96b
Create Date: 2026-09-29 15:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c58d1e7b0a94"
down_revision: Union[str, Sequence[str], None] = "a2e7c481f96b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_FROM_GROUP = "Stage 0"
_TO_GROUP = "Stage 0→1"

#: Not an ideation subject at all. Moved to the bank for founders who have
#: started, with the reason each one cannot be answered by someone who has not.
_RETAG: dict[str, str] = {
    "OPS-004": "customer support requests -- there are no customers",
    "PRD-006": "unit and integration testing -- there is no product to test",
    "PRD-007": "whether the roadmap follows validated needs -- there is no roadmap",
    "PRD-013": "a maintenance plan -- there is nothing built to maintain",
    "PRD-014": "rate how well the product solves the problem -- there is no product",
    "PRD-020": "staying on top of user needs for the product plan -- no users, no plan",
    "PRD-021": "how many active users or customers -- the answer is zero for everyone",
    "PSY-042": "how it feels when a deal falls through -- there are no deals",
    "IVA-022": "how customer criticism of what you built feels -- nothing is built",
    "IVA-061": "fear of investors who funded a direction -- nobody has funded anything",
}

#: The subject is valid at ideation; only the premise in the wording is not.
#: (code, exact old text, new text). Matched on the full old string so a
#: question someone has already reworded is left alone rather than overwritten.
_REWORD: tuple[tuple[str, str, str], ...] = (
    (
        "PSY-002",
        "How do you typically react when your startup hits a major setback?",
        "When something you are working on goes badly wrong, how do you usually react?",
    ),
    (
        "PSY-013",
        "What personal habits have changed since starting the venture — sleep, exercise?",
        "Since you started working on this, what has changed in how you sleep or look after yourself?",
    ),
    (
        "PSY-017",
        "Have you experienced any persistent insomnia or anxiety since starting?",
        "Since you started working on this, have you been sleeping badly or feeling anxious a lot?",
    ),
    (
        "PSY-147",
        "Does having a routine feel like the opposite of why you started this business?",
        "Does sticking to a routine feel like the opposite of why you started this?",
    ),
    (
        "IVA-030",
        "If a competing product launched tomorrow, how would your company respond?",
        "If someone launched a competing product tomorrow, what would you do?",
    ),
)

#: Questions outside Team & Leadership that still need other people to exist.
#: `d4a1f8c62b73` set the pillar 5 defaults; these two were never reached by it.
_NEEDS_A_TEAM: dict[str, str] = {
    "RSK-006": "asks what your team would list as risks",
    "IVA-060": "asks whether employees have become attached to existing work",
}


def upgrade() -> None:
    bind = op.get_bind()

    moved = bind.execute(
        sa.text(
            "UPDATE questions SET primary_stage_group = :to "
            "WHERE question_code = ANY(:codes) AND primary_stage_group = :frm"
        ),
        {"to": _TO_GROUP, "codes": list(_RETAG), "frm": _FROM_GROUP},
    ).rowcount
    print(f"[{revision}] {moved} of {len(_RETAG)} questions moved off the "
          f"ideation bank:")
    for code, why in _RETAG.items():
        print(f"[{revision}]   {code}: {why}")

    reworded = 0
    for code, old, new in _REWORD:
        n = bind.execute(
            sa.text(
                "UPDATE questions SET question_text = :new "
                "WHERE question_code = :code AND question_text = :old"
            ),
            {"new": new, "old": old, "code": code},
        ).rowcount
        if n:
            reworded += n
        else:
            # Not fatal: a database whose text has already been edited is not a
            # database this migration should overwrite.
            print(f"[{revision}] WARNING {code} did not match its expected "
                  "wording and was left alone")
    print(f"[{revision}] {reworded} of {len(_REWORD)} questions reworded to drop "
          "the assumption that the business exists")

    gated = bind.execute(
        sa.text(
            "UPDATE questions SET min_team_size = '2_5' "
            "WHERE question_code = ANY(:codes) AND min_team_size IS NULL"
        ),
        {"codes": list(_NEEDS_A_TEAM)},
    ).rowcount
    print(f"[{revision}] {gated} of {len(_NEEDS_A_TEAM)} questions outside Team & "
          "Leadership now need a team:")
    for code, why in _NEEDS_A_TEAM.items():
        print(f"[{revision}]   {code}: {why}")

    left = bind.execute(
        sa.text(
            "SELECT count(*) FROM questions WHERE primary_stage_group = :frm "
            "AND question_code = ANY(:codes)"
        ),
        {"frm": _FROM_GROUP, "codes": list(_RETAG)},
    ).scalar_one()
    if left:
        raise RuntimeError(f"{left} retargeted question(s) are still on the ideation bank")


def downgrade() -> None:
    bind = op.get_bind()

    bind.execute(
        sa.text(
            "UPDATE questions SET min_team_size = NULL WHERE question_code = ANY(:codes)"
        ),
        {"codes": list(_NEEDS_A_TEAM)},
    )
    for code, old, new in _REWORD:
        bind.execute(
            sa.text(
                "UPDATE questions SET question_text = :old "
                "WHERE question_code = :code AND question_text = :new"
            ),
            {"old": old, "new": new, "code": code},
        )
    bind.execute(
        sa.text(
            "UPDATE questions SET primary_stage_group = :frm "
            "WHERE question_code = ANY(:codes) AND primary_stage_group = :to"
        ),
        {"frm": _FROM_GROUP, "codes": list(_RETAG), "to": _TO_GROUP},
    )
