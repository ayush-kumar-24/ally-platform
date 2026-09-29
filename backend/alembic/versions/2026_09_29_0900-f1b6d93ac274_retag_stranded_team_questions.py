"""Move the Team & Leadership questions nothing could reach into the stage group
that asks about them, and size the ones that need a real organisation.

THE DEAD SHELF. 210 Team & Leadership questions carry
`primary_stage_group = 'Stage 0'`. The Stage 0 bank is served only to founders
at stage_order 1, and Part 3 withholds Team & Leadership from stage_order 1
twice over -- pillar 5 is not in `SCOPE_BY_STAGE_ORDER[1].pillars`, and
"Team & Leadership" is in its `withheld_categories`. So every one of those 210
questions was filtered out of every diagnosis that could have seen it. Not
under-used: unreachable, by anyone, since they were written.

Their text says where they belong. "Can your staff agree a discount without
asking you?", "When you last hired, how did you check they could actually do the
work?", "Is there a written rule for refunds or grace periods?" -- these
presuppose a business with customers and staff, which is Stage 0->1, not someone
with an idea. They were mis-tagged, so this retags them rather than widening
ideation's scope: an ideation founder still gets no team questions, which is the
correct behaviour and the one Part 3 asks for.

Checked before moving: no question text in this set already exists in the
Stage 0->1 Team & Leadership bank, so the retag introduces no duplicate. The 14
texts that repeat WITHIN the set are the industry templates ("Do you know what
an average refund costs you?" written once per industry); each is owned by its
own industry in `question_industry_mapping`, so one founder still sees one.

WHAT THIS UNSTRANDS. Migration d4a1f8c62b73 reviewed 210 Stage 0 Team &
Leadership questions and opened 45 of them to 'solo'. Every one of those 45 was
on this dead shelf, so the solo tier it built could not be served either. After
this retag they are reachable by a founder working alone at Validation,
Prototype/MVP and Early Traction -- which is where the founders who reported
being asked about their non-existent team actually are.

A SECOND DEAD SHELF IS LEFT ALONE, ON PURPOSE. 151 Stage 0 questions under
Revenue Maturity (pillar 3) are unreachable for the same reason. They are NOT
retagged here. Withholding revenue from an idea-stage founder is a deliberate
Part 3 rule, the same kind as the team one, and whether those questions are
mis-tagged or were written in anticipation needs their text read the way this
set's was. Moving 151 revenue questions into early-stage diagnoses as a side
effect of a team-scoping fix is not a call this migration should make.

SIZING WHAT NEEDS AN ORGANISATION. The same defect as the solo one, one size up:
every Team & Leadership question sat at '2_5', so a three-person company at
Growth stage was asked about leading through managers, succession planning and
career ladders. The 40 questions under `People Management Complexity` are split
by what they actually presuppose:

    11_25   managers who manage other people, and a ladder to be unclear about
    6_10    a real employee base, but no layer of management

Nothing above '11_25' is assigned. That is honest rather than incomplete: no
question in the bank distinguishes a 30-person company from a 60-person one, so
claiming it did would be fake precision.

Revision ID: f1b6d93ac274
Revises: d4a1f8c62b73
Create Date: 2026-09-29 09:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f1b6d93ac274"
down_revision: Union[str, Sequence[str], None] = "d4a1f8c62b73"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TEAM_PILLAR_ID = 5
_FROM_GROUP = "Stage 0"
_TO_GROUP = "Stage 0→1"          # 'Stage 0->1' with the real arrow
_SUBCATEGORY = "People Management Complexity"

#: The ten questions on the dead shelf whose codes are not prefixed `S0-`.
#: Recorded so downgrade() can put back exactly what upgrade() moved: the
#: reachable Stage 0->1 bank already holds TM-098 and up, and a bare "move the
#: TM-* rows back" would strand those instead.
_MOVED_TM: tuple[str, ...] = (
    "TM-003", "TM-005", "TM-009", "TM-011", "TM-016",
    "TM-020", "TM-022", "TM-095", "TM-096", "TM-097",
)

#: Reviewed as answerable by a founder working alone, from the 56 universal
#: Stage 0->1 Team & Leadership questions read individually. The Stage 0 bank's
#: 45 are already tagged by d4a1f8c62b73; these are the ones that were always
#: in the reachable bank and still sat at the '2_5' default.
_SOLO: tuple[str, ...] = (
    # Founder dependency: the answer "nobody" is the finding, not a blank.
    "TM-098",      # covering a function you are not equipped for
    "TM-099",      # anyone who pressure-tests your decisions
    "TM-100",      # growth capped by what one person can carry
    "TM-101",      # anyone carrying the emotional weight with you
    "TM-102",      # a past co-founder relationship that ended badly
    "TM-108",      # anyone outside the company reviewing major decisions
    "S01-TM-002",  # who has real authority besides you, on paper or in practice
    # Whether a rule exists, and what the founder assumes about needing one.
    "TM-111",      # does oversight feel like red tape
    "TM-112",      # are approval limits written down, or is it memory
    "TM-157",      # assuming tracking can wait until the team is bigger
)

#: The same review over the Stage 1->10+ bank's 204 universal Team &
#: Leadership questions. A founder can reach Growth or Maturity still working
#: alone -- a solo consultancy, a one-person SaaS -- and before this every one
#: of these was withheld from them, leaving the pillar unscorable.
#:
#: What makes these answerable alone is that they ask about the founder
#: themselves: whether the business survives their absence, whether everything
#: routes through them, whether they can let go of anything, whether a decision
#: was written down. The bank's other 183 need employees to exist -- payroll
#: systems, leave tracking, headcount, interview scorecards, meeting protocols,
#: co-founder agreements -- and stay at '2_5'.
_SOLO_GROWTH: tuple[str, ...] = (
    # Founder dependency and what happens without them.
    "S10-OPS-004",  # how long it runs if you disappear for two weeks
    "S10-OPS-006",  # the same problem resurfacing after you thought it fixed
    "S10-PSY-005",  # the last real day off without checking in
    "TM-109",       # does every approval route through you personally
    "TM-113",       # does money move with no second set of eyes
    # Delegation as a belief, which someone with nobody to delegate to still
    # holds -- and which is the thing keeping them solo.
    "TM-090", "TM-091", "TM-093", "TM-094", "TM-116",
    # Whether anything is written down, and whether it survived.
    "S10-TM-096",   # a decision second-guessed because nobody remembered why
    "S10-TM-109",   # a knowledge base that is actually current
    "S10-TM-111",   # a past decision quietly reversed, context never written
    "S10-TM-113",   # capturing lessons after a project
    "S10-OPS-001",  # is success in a role clear before interviewing for it
    # The founder's own conduct, environment and governance.
    "TM-114",       # investor or stakeholder updates on a real cadence
    "TM-115",       # undeclared related-party dealings
    "TM-120",       # is the day-to-day engaging or turning disengaging
    "TM-128",       # were the company's values ever actually defined
    "TM-129",       # does your own behaviour contradict what you stand for
    "TM-142",       # important information lost in the volume of messages
)

#: `People Management Complexity`, by what each problem actually presupposes.
#: Keyed on problem_name because the subcategory spans both bands.
_BY_PROBLEM_NAME: dict[str, str] = {
    # Needs managers managing other people, and a ladder to be unclear about.
    "Leading Through Managers Instead of Directly": "11_25",
    "New Managers Not Equipped to Lead": "11_25",
    "Internal Politics and Competing Interests": "11_25",
    "Role Ambiguity and Unclear Career Paths": "11_25",
    "No Organisational Health Monitoring": "11_25",
    # Needs employees, but not a layer of management.
    "No Performance Management System": "6_10",
    "Employee Disconnection and Morale Decline": "6_10",
    "Culture Failing to Scale Intentionally": "6_10",
    "Compensation and Equity Complexity": "6_10",
    "No Succession Planning or Key Person Risk": "6_10",
}


def upgrade() -> None:
    bind = op.get_bind()

    # --- guard: the retag must not create a duplicate ---------------------
    clash = bind.execute(
        sa.text(
            """
            SELECT count(*) FROM questions q
            JOIN problems p ON p.problem_id = q.problem_id
            WHERE p.pillar_id = :pillar AND q.primary_stage_group = :frm
              AND q.question_text IN (
                    SELECT q2.question_text FROM questions q2
                    JOIN problems p2 ON p2.problem_id = q2.problem_id
                    WHERE p2.pillar_id = :pillar AND q2.primary_stage_group = :to
              )
            """
        ),
        {"pillar": _TEAM_PILLAR_ID, "frm": _FROM_GROUP, "to": _TO_GROUP},
    ).scalar_one()
    if clash:
        raise RuntimeError(
            f"{clash} question(s) would duplicate text already in the {_TO_GROUP} "
            "bank; the two banks have diverged since this was written and the "
            "overlap needs reading before anything moves"
        )

    # --- guard: the set moving is the one this migration was written against
    unexpected = bind.execute(
        sa.text(
            """
            SELECT q.question_code FROM questions q
            JOIN problems p ON p.problem_id = q.problem_id
            WHERE p.pillar_id = :pillar AND q.primary_stage_group = :frm
              AND q.question_code NOT LIKE 'S0-%' AND q.question_code <> ALL(:tm)
            ORDER BY q.question_code
            """
        ),
        {"pillar": _TEAM_PILLAR_ID, "frm": _FROM_GROUP, "tm": list(_MOVED_TM)},
    ).scalars().all()
    if unexpected:
        raise RuntimeError(
            "questions on the dead shelf that downgrade() could not put back: "
            f"{unexpected}"
        )

    # --- the retag --------------------------------------------------------
    moved = bind.execute(
        sa.text(
            """
            UPDATE questions q SET primary_stage_group = :to
            FROM problems p
            WHERE p.problem_id = q.problem_id
              AND p.pillar_id = :pillar
              AND q.primary_stage_group = :frm
            """
        ),
        {"pillar": _TEAM_PILLAR_ID, "frm": _FROM_GROUP, "to": _TO_GROUP},
    ).rowcount
    print(f"[{revision}] {moved} Team & Leadership questions moved from "
          f"'{_FROM_GROUP}' to '{_TO_GROUP}'")

    left = bind.execute(
        sa.text(
            "SELECT count(*) FROM questions q JOIN problems p "
            "ON p.problem_id = q.problem_id "
            "WHERE p.pillar_id = :pillar AND q.primary_stage_group = :frm"
        ),
        {"pillar": _TEAM_PILLAR_ID, "frm": _FROM_GROUP},
    ).scalar_one()
    if left:
        raise RuntimeError(f"{left} Team & Leadership questions are still on the dead shelf")

    # --- the reviewed solo list in the bank that was always reachable -----
    reviewed = list(_SOLO) + list(_SOLO_GROWTH)
    opened = bind.execute(
        sa.text("UPDATE questions SET min_team_size = 'solo' WHERE question_code = ANY(:codes)"),
        {"codes": reviewed},
    ).rowcount
    print(f"[{revision}] {opened} of {len(reviewed)} reviewed questions opened to "
          f"'solo' ({len(_SOLO)} at Stage 0->1, {len(_SOLO_GROWTH)} at Stage 1->10+)")
    if opened != len(reviewed):
        missing = bind.execute(
            sa.text(
                "SELECT c FROM unnest(CAST(:codes AS text[])) AS c "
                "WHERE c NOT IN (SELECT question_code FROM questions)"
            ),
            {"codes": reviewed},
        ).scalars().all()
        print(f"[{revision}] WARNING not in this database: {sorted(missing)}")

    stray = bind.execute(
        sa.text(
            """
            SELECT q.question_code FROM questions q
            JOIN problems p ON p.problem_id = q.problem_id
            WHERE q.question_code = ANY(:codes) AND p.pillar_id <> :pillar
            """
        ),
        {"codes": reviewed, "pillar": _TEAM_PILLAR_ID},
    ).scalars().all()
    if stray:
        raise RuntimeError(f"reviewed as solo but not Team & Leadership: {sorted(stray)}")

    # --- size the questions that need a real organisation -----------------
    sized = bind.execute(
        sa.text(
            """
            UPDATE questions q SET min_team_size = v.band
            FROM problems p,
                 (SELECT * FROM unnest(CAST(:names AS text[]), CAST(:bands AS text[]))
                    AS t(name, band)) v
            WHERE p.problem_id = q.problem_id
              AND p.pillar_id = :pillar
              AND p.subcategory = :sub
              AND p.problem_name = v.name
            """
        ),
        {
            "names": list(_BY_PROBLEM_NAME),
            "bands": list(_BY_PROBLEM_NAME.values()),
            "pillar": _TEAM_PILLAR_ID,
            "sub": _SUBCATEGORY,
        },
    ).rowcount
    print(f"[{revision}] {sized} questions under '{_SUBCATEGORY}' now require "
          "a real organisation")

    for band, n in bind.execute(
        sa.text(
            """
            SELECT q.min_team_size, count(*) FROM questions q
            JOIN problems p ON p.problem_id = q.problem_id
            WHERE p.pillar_id = :pillar GROUP BY 1 ORDER BY 1
            """
        ),
        {"pillar": _TEAM_PILLAR_ID},
    ).all():
        print(f"[{revision}]   {band}: {n}")


def downgrade() -> None:
    bind = op.get_bind()

    # Undo the sizing first, back to the pillar's reviewed default.
    bind.execute(
        sa.text(
            """
            UPDATE questions q SET min_team_size = '2_5'
            FROM problems p
            WHERE p.problem_id = q.problem_id
              AND p.pillar_id = :pillar AND p.subcategory = :sub
            """
        ),
        {"pillar": _TEAM_PILLAR_ID, "sub": _SUBCATEGORY},
    )
    bind.execute(
        sa.text("UPDATE questions SET min_team_size = '2_5' WHERE question_code = ANY(:codes)"),
        {"codes": list(_SOLO) + list(_SOLO_GROWTH)},
    )

    # Then the retag, reversed by exactly what upgrade() moved: every `S0-`
    # coded pillar 5 question plus the ten recorded above. Not a bare
    # (pillar, group) predicate -- that would also sweep back TM-098 and the
    # rest of the bank that was in 'Stage 0->1' all along.
    bind.execute(
        sa.text(
            """
            UPDATE questions q SET primary_stage_group = :frm
            FROM problems p
            WHERE p.problem_id = q.problem_id
              AND p.pillar_id = :pillar
              AND q.primary_stage_group = :to
              AND (q.question_code LIKE 'S0-%' OR q.question_code = ANY(:tm))
            """
        ),
        {"pillar": _TEAM_PILLAR_ID, "frm": _FROM_GROUP, "to": _TO_GROUP,
         "tm": list(_MOVED_TM)},
    )
