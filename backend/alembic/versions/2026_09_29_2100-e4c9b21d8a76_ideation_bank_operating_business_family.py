"""Move the whole small-operating-business family out of the ideation bank.

c58d1e7b0a94 fixed seventeen questions that presumed a business an idea-stage
founder has not started. It checked the 183 legacy-coded questions and took the
988 `S0-` coded ones on trust, on the grounds that they were written for the
Stage 0 bank on purpose. That was right about most of them and wrong about a
whole family.

Collapsing the 1,127 `S0-` questions by their code shape gives 148 templates,
and the templates fall into two groups that were clearly written by different
hands for different founders:

    S0-XXX-0nn      An idea, nothing built. "Have you actually spoken to a
    S0-IVA-nnn      farmer about this idea, or is this based on what you assume
    S0-BPL-nnn      they'd want?", "What's the smallest version of this you
                    could build to learn something?". Correct, and untouched.

    S0-XXX-1nn      A business already trading. "How many hours a week do you
    S0-XXX-2nn      spend running the business rather than serving clients?",
    S0-XXX-3nn      "How did you arrive at your current price list?", "Which of
                    your services makes the most money per hour of chair time?",
                    "If your dispatcher left, what would you lose?", "Do you
                    record which component failed on each repair?"

The second family has 410 questions still in the ideation bank -- 200 under
Founder Readiness and 210 under Strategic Clarity, both pillars that ideation
fully assesses, so every one of them was reachable. f1b6d93ac274 already moved
this family's Team & Leadership members for the same reason; this is the rest
of it.

`S0-IVA-1nn` IS NOT IN THE FAMILY, despite matching the number shape. Those are
"Have you studied a failed attempt at something similar?" and "When you feel
stuck, is your default to think it through or to just start doing something?" --
idea-stage questions that happen to be numbered past 100. The family is defined
by an INDUSTRY prefix plus the number, and the nine non-industry prefixes are
excluded by name. A first pass matching on the number alone swept up fifteen of
them.

ONE DUPLICATE IS CREATED AND ACCEPTED. S0-FNB-105-1 and the Stage 0->1 bank's
S01-FNB-011 are both "What share of your orders comes through delivery apps?",
and both belong to foodtech, so one founder can now draw both. The session's
near-repeat guard (`DIAGNOSIS_REPEAT_MAX_DISTANCE`, cosine distance over the
question embeddings) catches an identical pair trivially. Recorded here because
it is a consequence of this migration rather than something it found.
S0-MFG-302-2 and S01-TRV-302-2 also share text but belong to different
industries, so the industry gate keeps them apart.

ALSO: the twelve `BMD-` Business Model Design questions. They sit under Revenue
Maturity, which ideation withholds entirely, so they have never been reachable
by anyone -- the same dead shelf f1b6d93ac274 found for Team & Leadership.
Several presume a price already being charged ("besides how you charge today",
"has your way of charging changed since you first started"). Moving them to
Stage 0->1 costs ideation nothing, because ideation could not see them, and
makes them reachable by the founders they were written for.

NOT TOUCHED: the other 139 questions on that same Revenue Maturity shelf, the
`S0-XXX-011..015` set. Unlike the BMD twelve those ARE idea-stage questions --
"Where would you actually get your product from?", "How would the product reach
the customer, and who pays for that?", "What happens if a customer wants to
return the product?" -- and they are unreachable only because their problems are
filed under Revenue Maturity while ideation withholds that pillar. Retagging
them would make them reachable at a stage where the founder already knows the
answer, which is worse than leaving them where they are. Making them reachable
at ideation instead means changing what ideation assesses, which is a product
decision and not one a migration should take quietly.

Revision ID: e4c9b21d8a76
Revises: d71a4e8c3f05
Create Date: 2026-09-29 21:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e4c9b21d8a76"
down_revision: Union[str, Sequence[str], None] = "d71a4e8c3f05"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_FROM_GROUP = "Stage 0"
_TO_GROUP = "Stage 0→1"

#: `S0-<INDUSTRY>-<1|2|3>nn` with an optional `-n` suffix. The number shape
#: alone is not enough -- see the note on S0-IVA-1nn above.
_FAMILY = r"^S0-[A-Z]{3}-[123][0-9]{2}(-[0-9])?$"

#: Three-letter codes in the `S0-` namespace that name a SUBJECT rather than an
#: industry. Questions under these were written for the idea-stage bank whatever
#: their number, so they are never part of the operating family.
_NOT_INDUSTRIES: tuple[str, ...] = (
    "IVA", "BPL", "PRD", "PSY", "OPS", "TCI", "CMA", "RSK", "SCL",
)

#: Business Model Design, on the Revenue Maturity shelf ideation cannot see.
_BMD_PREFIX = "BMD-"

#: What the family should come to, so a data set that has drifted is obvious
#: rather than silently half-moved.
_EXPECTED_FAMILY = 410


def upgrade() -> None:
    bind = op.get_bind()

    params = {
        "frm": _FROM_GROUP, "to": _TO_GROUP,
        "family": _FAMILY, "not_industries": list(_NOT_INDUSTRIES),
    }
    found = bind.execute(
        sa.text(
            """
            SELECT count(*) FROM questions
            WHERE primary_stage_group = :frm
              AND question_code ~ :family
              AND substring(question_code from 4 for 3) <> ALL(:not_industries)
            """
        ),
        params,
    ).scalar_one()
    print(f"[{revision}] operating-business family on the ideation bank: {found} "
          f"(expected {_EXPECTED_FAMILY})")
    if found != _EXPECTED_FAMILY:
        # Not fatal -- a database built from a different batch set holds a
        # different count -- but a silent mismatch is how a half-move happens.
        print(f"[{revision}] WARNING the family is not the size this migration "
              "was written against; check the code shapes before trusting it")

    moved = bind.execute(
        sa.text(
            """
            UPDATE questions SET primary_stage_group = :to
            WHERE primary_stage_group = :frm
              AND question_code ~ :family
              AND substring(question_code from 4 for 3) <> ALL(:not_industries)
            """
        ),
        params,
    ).rowcount
    print(f"[{revision}] {moved} moved to '{_TO_GROUP}'")

    bmd = bind.execute(
        sa.text(
            "UPDATE questions SET primary_stage_group = :to "
            "WHERE primary_stage_group = :frm AND question_code LIKE :pfx"
        ),
        {"frm": _FROM_GROUP, "to": _TO_GROUP, "pfx": f"{_BMD_PREFIX}%"},
    ).rowcount
    print(f"[{revision}] {bmd} Business Model Design questions moved off the "
          "Revenue Maturity shelf nobody could reach")

    remaining = bind.execute(
        sa.text(
            """
            SELECT count(*) FROM questions
            WHERE primary_stage_group = :frm
              AND question_code ~ :family
              AND substring(question_code from 4 for 3) <> ALL(:not_industries)
            """
        ),
        params,
    ).scalar_one()
    if remaining:
        raise RuntimeError(f"{remaining} family question(s) are still on the ideation bank")

    for pillar, n in bind.execute(
        sa.text(
            """
            SELECT p.pillar_id, count(*) FROM questions q
            JOIN problems p ON p.problem_id = q.problem_id
            WHERE q.primary_stage_group = :frm GROUP BY 1 ORDER BY 1
            """
        ),
        {"frm": _FROM_GROUP},
    ).all():
        print(f"[{revision}]   ideation bank, pillar {pillar}: {n}")


def downgrade() -> None:
    bind = op.get_bind()
    # EXCLUDE PILLAR 5. This family's Team & Leadership members are in
    # 'Stage 0->1' because f1b6d93ac274 put them there, not because this
    # migration did -- upgrade() found none of them on the ideation bank to
    # move. A downgrade matching the family alone sweeps those 200 back to
    # 'Stage 0' as well, silently undoing the earlier migration and returning
    # them to the shelf no founder can reach. Each migration puts back only
    # what it took.
    bind.execute(
        sa.text(
            """
            UPDATE questions q SET primary_stage_group = :frm
            FROM problems p
            WHERE p.problem_id = q.problem_id
              AND p.pillar_id <> :team_pillar
              AND q.primary_stage_group = :to
              AND q.question_code ~ :family
              AND substring(q.question_code from 4 for 3) <> ALL(:not_industries)
            """
        ),
        {
            "frm": _FROM_GROUP, "to": _TO_GROUP, "team_pillar": 5,
            "family": _FAMILY, "not_industries": list(_NOT_INDUSTRIES),
        },
    )
    bind.execute(
        sa.text(
            "UPDATE questions SET primary_stage_group = :frm "
            "WHERE primary_stage_group = :to AND question_code LIKE :pfx"
        ),
        {"frm": _FROM_GROUP, "to": _TO_GROUP, "pfx": f"{_BMD_PREFIX}%"},
    )
