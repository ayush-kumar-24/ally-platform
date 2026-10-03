"""Fifty-three questions outside Team & Leadership that presume a team.

d4a1f8c62b73 fixed the diagnosis asking solo founders about staff they do not
have. It did it by giving every Team & Leadership question a `min_team_size`,
because all three of that pillar's Business DNA dimensions presuppose other
people. That was right for pillar 5 and it stopped there.

These thirty-four sit in the other five pillars -- Operations, Scaling, Sales
Execution, Founder Psychology, Go-To-Market, Product -- carry no team
requirement at all, and presume one anyway:

    Are your managers being trained and given the power to take full charge?
    Does your product team have clear, ranked priorities?
    How comfortable are you managing your staff?
    Does your sales team tend to overestimate how likely a deal will close?

Found testing a four-person founder at Growth, then confirmed against a SOLO
founder at Growth: twenty-five of them were sitting in his candidate pool. He
has no sales team, no managers and no staff. This is the original defect
verbatim, in the pillars the original fix did not reach.

THE SET GREW THREE TIMES WHILE THIS WAS BEING WRITTEN, which is the honest
history and the reason the guard matters more than the list. The first sweep
found thirty-four. The guard added alongside this migration found two more I had
walked straight past: I matched "your staff" as a whole word and so missed "your
staffing model", and "your leaders" and so missed "your leadership's attention".
Widening once more for people named by their JOB rather than as a team --
"your salespeople", "your reps", "your drivers", "your teachers" -- found
seventeen more, including a founder's own drivers and tutors.

Fifty-three now. The number is not the point: a hand-written pattern has been
narrower than the thing it describes at every attempt, so the guard is set to
the widest pattern and will fail until each new question is read and sized,
rather than being trusted to have found them all today.

NOTE THE OVERLAP WITH requires_operating_role. S01-DLV-006, S01-DLV-013 and
S01-LOG-009 already carry it, which withholds them from somebody selling
software to a trade. That is a different question from this one: a founder who
really does run deliveries, alone in his own van, still has no "drivers". Both
axes apply, independently, and neither makes the other redundant.

THREE LEVELS, BY WHAT THE QUESTION ACTUALLY NEEDS, read one at a time:

  '2_5' -- anyone but a founder working alone. "Are your staff trained on
  emergency response?" needs somebody other than you; two people is enough.

  '6_10' -- a named FUNCTION. "Your sales team", "your product team", "your
  finance team" is a group that has specialised, and at two to five people
  nobody has. S10-SAL-016 goes further and asks about "newer reps", which needs
  several.

  '11_25' -- a MANAGEMENT LAYER. "Your managers", "your leaders", "which
  decisions your managers can make without checking with you". You do not have
  managers at ten people; you have colleagues. This matches the five
  manager questions d4a1f8c62b73 already set to '11_25', so the bank stays
  consistent with itself rather than acquiring a second convention.

WHY NOT A KEYWORD RULE. "Your customers" and "your team" look alike to a regex
and are nothing alike in meaning -- the bank says "your customers" everywhere
to mean TARGET customers, of a founder who has none yet. Every one of these
thirty-four was read. That discipline is the same one d4a1f8c62b73 and
a6f3d2c81b47 record, both of which were wrong in both directions when screened
by pattern.

Revision ID: a95e3d17c284
Revises: f74b2e9c1a60
Create Date: 2026-10-03 11:00:00.000000
"""
from __future__ import annotations

from alembic import op
from sqlalchemy import text

revision = "a95e3d17c284"
down_revision = "f74b2e9c1a60"
branch_labels = None
depends_on = None

#: Needs somebody other than the founder. Two people is enough.
_NEEDS_ANYONE = (
    "S01-AUT-203-2", "S01-BPC-201-2", "S01-PSY-027", "S01-SPF-020", "S10-TRV-022",
    # "Is your staffing model written as roles and hours, or around the people
    # you have?" -- a staffing model needs staff. Missed by my own sweep, which
    # bounded "your staff" as a whole word and so skipped "your staffing";
    # caught by test_no_question_presuming_a_team_is_left_unsized.
    "S01-FNB-106-2",
    # People the founder employs, named by their job rather than as a "team":
    # drivers, teachers, a team lead. Same presumption, and a lone operator --
    # one driver, one tutor -- has none of them.
    "S0-GAM-309-2", "S0-MKT-309-2", "S01-DLV-006", "S01-DLV-013",
    "S01-EDU-307-1", "S01-LOG-009", "S10-EDU-002", "S10-EDU-003",
)

#: Needs a named function -- a sales, product, engineering or finance TEAM.
_NEEDS_A_FUNCTION = (
    "MEX-069", "MEX-171", "S10-FIN-115", "S10-GTM-067", "S10-PRD-013",
    "S10-PRD-029", "S10-PRD-052", "S10-SAL-002", "S10-SAL-008", "S10-SAL-016",
    "S10-SLX-031", "S10-SLX-034", "S10-SLX-035", "S10-SLX-044", "SCL-111",
    "SCL-115", "SCL-126", "SCL-129", "SCL-132",
    # "Your salespeople", "your reps" -- the same function, named by its people
    # instead of as a team. SCL-128 goes further and assumes a commission plan.
    "S10-SAL-009", "S10-SAL-015", "S10-SLX-032", "S10-SLX-036", "S10-SLX-042",
    "S10-SLX-050", "S10-SLX-052", "SCL-099", "SCL-128",
)

#: Needs a management layer -- "your managers", "your leaders".
_NEEDS_MANAGERS = (
    "OPS-092", "S10-PRD-071", "S10-PRD-087", "S10-PRD-156", "S10-PSY-014",
    "S10-SLX-062", "SCL-063", "SCL-082", "SCL-084", "SCL-106",
    # "Is your leadership's attention spread across too many markets?" -- same
    # miss, "your leadership's" rather than "your leaders".
    "SCL-216",
)

_BANDS = (("2_5", _NEEDS_ANYONE), ("6_10", _NEEDS_A_FUNCTION),
          ("11_25", _NEEDS_MANAGERS))


def _set(codes: tuple[str, ...], band: str | None) -> None:
    """Set `min_team_size`, skipping codes this catalogue does not have.

    Tolerant for the reason 8b63ca0f gives: raising inside `alembic upgrade
    head` stops the whole release, and a question that is not here cannot be
    asked either, so failing to size it withholds nothing from nobody. Not one
    code present still raises -- that is the wrong catalogue, not drift.
    """
    bind = op.get_bind()
    present = {
        row[0]
        for row in bind.execute(
            text("SELECT question_code FROM questions WHERE question_code = ANY(:codes)"),
            {"codes": list(codes)},
        ).all()
    }
    missing = sorted(set(codes) - present)
    if not present:
        raise RuntimeError(
            f"None of the {len(codes)} questions {revision} names are in this "
            "catalogue. That is the wrong database, not drift."
        )
    bind.execute(
        text(
            "UPDATE questions SET min_team_size = :band, updated_at = now() "
            "WHERE question_code = ANY(:codes)"
        ),
        {"band": band, "codes": sorted(present)},
    )
    print(
        f"{revision}: min_team_size={band!r} on {len(present)} of {len(codes)}"
        + (f"; not in this catalogue: {', '.join(missing)}" if missing else "")
    )


def upgrade() -> None:
    for band, codes in _BANDS:
        _set(codes, band)


def downgrade() -> None:
    # Every one of these carried NULL before this migration -- that is what made
    # them reachable by a solo founder, and what the sweep found them by.
    for _band, codes in _BANDS:
        _set(codes, None)
