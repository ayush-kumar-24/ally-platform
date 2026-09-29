"""Widen the solo tier in the Stage 1->10+ bank.

f1b6d93ac274 opened 21 of that bank's 204 universal Team & Leadership
questions to 'solo'. That clears the three-answer floor, so the pillar is
scored rather than withheld -- but 21 questions have to cover four stages
(Growth, Expansion, Maturity, Exit), which means a founder working alone at
Growth and the same founder at Exit see close to the same set.

A second read of the 183 that stayed at '2_5' found ten more that a founder
with nobody else can answer as asked. They were missed the first time because
each mentions a team, a hire or "people" somewhere in the sentence -- and a
first pass that screens on those words throws away exactly the questions where
the founder IS the whole team ("what breaks if the one person who knows it
left tomorrow?") or where the question is explicitly hypothetical ("if someone
else ran this business your way for a month, what would feel wrong?").

Still deliberately NOT opened, so the line stays where f1b6d93ac274 put it:

  * Anything needing a past hire to describe -- "look at your last 3 hires",
    "the last leadership hire made too quickly". A founder who has never hired
    has nothing to say, and the diagnosis reads that blank as a gap.
  * Anything about how an existing team feels, behaves or is paid -- morale,
    career ladders, meeting culture, reward systems, payroll and HR tooling.
  * "Are you still doing tasks yourself out of old habit, even though the team
    has grown past needing that?" and its family: the premise is a team that
    grew, which is the opposite of the founder being asked.

Revision ID: a2e7c481f96b
Revises: f1b6d93ac274
Create Date: 2026-09-29 11:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a2e7c481f96b"
down_revision: Union[str, Sequence[str], None] = "f1b6d93ac274"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TEAM_PILLAR_ID = 5

#: Ten more, grouped by what makes each answerable with nobody else there.
_SOLO_GROWTH_2: tuple[str, ...] = (
    # The founder IS the "one person who knows it" and the "people's heads".
    # Asked of someone alone, these read as the bus-factor questions they are.
    "S10-OPS-002",  # top three recurring operations: documented, or in heads
    "S10-TM-093",   # key process knowledge documented, or in heads
    "S10-TM-095",   # major decisions documented, or the reasoning lost
    "S10-TM-103",   # what breaks if the one person who knows it left tomorrow
    # Explicitly hypothetical -- the question supplies the other person.
    "S10-TM-003",   # a responsibility you could not watch done differently
    "S10-TM-006",   # if someone ran this your way for a month, what feels wrong
    "S10-TM-050",   # a capability needed in twelve months nobody here has
    # Beliefs about delegating, which someone with nobody to delegate to still
    # holds -- and which are often the reason they are still alone.
    "S10-OPS-005",  # would someone else's mistake cost more than doing it all
    "S10-TM-042",   # avoiding hiring someone more capable than you
    "TM-089",       # the difference between managing and supervising
)


def upgrade() -> None:
    bind = op.get_bind()

    opened = bind.execute(
        sa.text(
            "UPDATE questions SET min_team_size = 'solo' "
            "WHERE question_code = ANY(:codes) AND min_team_size <> 'solo'"
        ),
        {"codes": list(_SOLO_GROWTH_2)},
    ).rowcount
    print(f"[{revision}] {opened} further questions opened to 'solo'")

    stray = bind.execute(
        sa.text(
            """
            SELECT q.question_code FROM questions q
            JOIN problems p ON p.problem_id = q.problem_id
            WHERE q.question_code = ANY(:codes)
              AND (p.pillar_id <> :pillar OR q.primary_stage_group <> :group)
            """
        ),
        {
            "codes": list(_SOLO_GROWTH_2),
            "pillar": _TEAM_PILLAR_ID,
            "group": "Stage 1→10+",
        },
    ).scalars().all()
    if stray:
        raise RuntimeError(
            "reviewed against the Stage 1->10+ Team & Leadership bank but not "
            f"in it: {sorted(stray)}"
        )

    total = bind.execute(
        sa.text(
            """
            SELECT count(*) FROM questions q
            JOIN problems p ON p.problem_id = q.problem_id
            WHERE p.pillar_id = :pillar AND q.primary_stage_group = :group
              AND q.min_team_size = 'solo'
            """
        ),
        {"pillar": _TEAM_PILLAR_ID, "group": "Stage 1→10+"},
    ).scalar_one()
    print(f"[{revision}] a founder working alone at Growth and beyond now has "
          f"{total} Team & Leadership questions")


def downgrade() -> None:
    op.get_bind().execute(
        sa.text(
            "UPDATE questions SET min_team_size = '2_5' WHERE question_code = ANY(:codes)"
        ),
        {"codes": list(_SOLO_GROWTH_2)},
    )
