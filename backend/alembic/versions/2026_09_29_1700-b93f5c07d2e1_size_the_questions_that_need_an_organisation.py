"""Make the top three team-size answers mean something.

Onboarding offers six answers -- Just me, 2-5, 6-10, 11-25, 26-50, More than
50. Measured against the bank after a2e7c481f96b, picking "26-50 people" and
picking "11-25 people" produced an identical set of questions, because nothing
was labelled above '11_25'. Two of the six answers were decoration.

Worse, the questions that DO presuppose an organisation were mostly invisible
to the gate. `d4a1f8c62b73` set defaults for pillar 5, so anything about a
leadership team or several departments filed under Revenue Maturity, Market
Clarity, Product & Execution or Founder Readiness carried no band at all.
A three-person company was being asked

    S10-PSY-015  Look at your leadership team. Which of them still don't have
                 real authority to decide without checking with you?
    S10-OPE-009  If two department heads both wanted resources for competing
                 priorities this month, is there a clear process for deciding?
    SCL-070      Is there any structured cadence -- an all-hands, team updates,
                 regular check-ins -- for sharing information across the company?

Same defect as the solo one, two sizes up, and in the pillars nobody had swept.

THE TWO LINES DRAWN HERE, and they are drawn on what the question's own words
require rather than on a guess about company size:

    11_25   presupposes a LEADERSHIP TEAM -- several managers who decide
            things, whom the founder delegates to and can be disagreed with by.
    26_50   presupposes SEVERAL DISTINCT TEAMS OR DEPARTMENTS -- plural teams
            with their own norms, department heads competing for resources,
            information that has to travel company-wide.

A fifteen-person company has a leadership team and does not have departments,
which is exactly the distinction the two bands need to carry.

NOTHING IS LABELLED '50_plus', AND THAT STAYS TRUE. No question in the bank
distinguishes a thirty-person company from a sixty-person one. Inventing a line
there would be fake precision, so "More than 50" keeps behaving like "26-50" --
the difference is recorded on the founder's profile, where it is still worth
having, and simply does not change which questions are asked.

WHAT WAS DELIBERATELY NOT MATCHED. Two questions use the word "department"
about someone else's organisation and stay open to everyone:

    SAL-023      Who typically pays for your product -- end-user, department,
                 or corporate buyer?  (the CUSTOMER's department)
    S01-FIN-020  Is your budget broken down by category or department...?
                 ("or category" is the small-business answer)

Matching on the word rather than the meaning would have withheld both from
every founder under 26 people, including a solo founder selling to enterprises.

Revision ID: b93f5c07d2e1
Revises: c58d1e7b0a94
Create Date: 2026-09-29 17:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b93f5c07d2e1"
# Runs after the plain-language pass rather than beside it. Both branched
# from c58d1e7b0a94; this chain was re-pointed so there is one line of
# migrations instead of two heads. Order is safe either way -- that pass
# rewrites question TEXT and everything below matches on question_code.
down_revision: Union[str, Sequence[str], None] = "c5e18b3f9a04"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

#: Presupposes a leadership team: several managers the founder delegates to,
#: who hold authority and can disagree with them.
_NEEDS_A_LEADERSHIP_TEAM: tuple[str, ...] = (
    "S10-FIN-044",  # regular financial review with your leadership team
    "S10-FIN-075",  # is your leadership team aligned on the runway number
    "S10-GTM-013",  # does your leadership team understand the unit economics
    "S10-GTM-056",  # when did your leadership team last sit in on a discovery call
    "S10-OPE-001",  # does your leadership team evaluate opportunities consistently
    "S10-OPE-016",  # would your leadership team all name the same top priority
    "S10-PRD-045",  # a dashboard your leadership team checks for product health
    "S10-PSY-015",  # which of your leadership team still lack real authority
    "S10-PSY-020",  # do you trust your leadership team with judgment calls
    "S10-PSY-021",  # would your leadership team tell you they disagreed
    "S10-PSY-040",  # has anyone on your leadership team raised your time management
    "S10-TM-037",   # does your leadership team have the expertise now needed
    "S10-TM-038",   # a skill gap on your leadership team nobody has addressed
    "S10-TM-041",   # your leadership team mapped against the next two years
    "S10-TM-132",   # do you know your headcount and org structure with certainty
)

#: Presupposes several distinct teams or departments -- plural teams with their
#: own norms and tools, department heads with competing claims, information
#: that has to be moved company-wide.
_NEEDS_SEVERAL_TEAMS: tuple[str, ...] = (
    "SCL-067",      # loyalty to their own department over the company
    "SCL-068",      # different teams using tools that do not talk to each other
    "SCL-070",      # an all-hands or company-wide sharing cadence
    "SCL-166",      # teams competing for budget or headcount
    "SCL-167",      # a process for when two teams disagree
    "S10-FIN-092",  # tracking that still varies by team or department
    "S10-GTM-068",  # would different department heads describe the ICP alike
    "S10-OPE-009",  # two department heads wanting the same resources
    "S10-PRD-078",  # could every department head describe the pain point alike
    "S10-PRD-140",  # do different teams or squads follow a consistent process
    "S10-PRD-141",  # weak coordination between teams causing duplicated work
    "S10-PRD-157",  # a single source of truth for metrics across teams
    "S10-PRD-182",  # data ownership falling into a gap between teams
    "S10-PSY-017",  # do your department heads work from outcomes or assigned tasks
    "S10-TM-073",   # recognising achievement consistently across teams
    "S10-TM-078",   # managers across your organisation applying one hiring bar
    "S10-TM-086",   # hiring standards differing across departments
    "S10-TM-112",   # different teams following different communication norms
    "S10-TM-134",   # each manager tracking their own team's leave separately
    "TM-148",       # parts of your team operating without cross-functional contact
)

_ASSIGNMENTS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("11_25", _NEEDS_A_LEADERSHIP_TEAM),
    ("26_50", _NEEDS_SEVERAL_TEAMS),
)


def upgrade() -> None:
    bind = op.get_bind()

    for band, codes in _ASSIGNMENTS:
        found = bind.execute(
            sa.text("SELECT count(*) FROM questions WHERE question_code = ANY(:codes)"),
            {"codes": list(codes)},
        ).scalar_one()
        if found != len(codes):
            missing = bind.execute(
                sa.text(
                    "SELECT c FROM unnest(CAST(:codes AS text[])) AS c "
                    "WHERE c NOT IN (SELECT question_code FROM questions)"
                ),
                {"codes": list(codes)},
            ).scalars().all()
            # Not fatal: a database built from a different batch set holds
            # fewer questions. Silence would be the problem.
            print(f"[{revision}] WARNING not in this database: {sorted(missing)}")

        changed = bind.execute(
            sa.text(
                "UPDATE questions SET min_team_size = :band "
                "WHERE question_code = ANY(:codes) "
                "AND (min_team_size IS DISTINCT FROM :band)"
            ),
            {"band": band, "codes": list(codes)},
        ).rowcount
        print(f"[{revision}] {changed} questions now need '{band}'")

    for band, n in bind.execute(
        sa.text(
            "SELECT coalesce(min_team_size, '(none)'), count(*) FROM questions "
            "GROUP BY 1 ORDER BY 2 DESC"
        )
    ).all():
        print(f"[{revision}]   {band}: {n}")


def downgrade() -> None:
    bind = op.get_bind()
    # Back to what each carried before: the Team & Leadership codes were at the
    # pillar's '2_5' default, and everything outside that pillar had no band.
    bind.execute(
        sa.text(
            """
            UPDATE questions q SET min_team_size =
                CASE WHEN p.pillar_id = 5 THEN '2_5' ELSE NULL END
            FROM problems p
            WHERE p.problem_id = q.problem_id AND q.question_code = ANY(:codes)
            """
        ),
        {"codes": list(_NEEDS_A_LEADERSHIP_TEAM) + list(_NEEDS_SEVERAL_TEAMS)},
    )
    # SCL-166 and SCL-167 are pillar 5 but were at '11_25', not the default.
    bind.execute(
        sa.text(
            "UPDATE questions SET min_team_size = '11_25' "
            "WHERE question_code = ANY(:codes)"
        ),
        {"codes": ["SCL-166", "SCL-167"]},
    )
