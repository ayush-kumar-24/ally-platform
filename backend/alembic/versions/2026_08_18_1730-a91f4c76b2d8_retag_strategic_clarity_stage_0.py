"""Fix what a Stage 0 founder is asked about Strategic Clarity.

Companion to f6d2a81c53e7 (Market Clarity). Same audit, different pillar --
and this one was the worst of the six, because the questions were not merely
thin, they were unanswerable.

A Stage 0 founder has an idea and has not built or sold anything (the
Stage-Adaptive doc's Priya). Strategic Clarity offered them exactly eight
questions, and every one presupposed a funded, operating company:

    "How did you arrive at your current or desired valuation?"
    "Do you have any letters of intent or term sheets from investors already?"
    "Is your approach to backups and disaster recovery based on your own risk
     tolerance...?"

Meanwhile the questions that ARE the doc's Stage 0 zone -- "Founder clarity &
conviction gaps... fear masquerading as 'more research needed'" -- were all
locked to Stage 0->1 and unreachable:

    "What usually stops you from planning, even when you know you should?"
    "What has to be true for your current plan to work? Name your biggest
     assumption."
    "What would you do if that assumption turned out to be wrong?"

So the fix runs in BOTH directions, and each direction is a genuine mis-tag
rather than a rebalancing convenience.

IN  (Stage 0->1 -> Stage 0), whole problems, 20 questions:
    139 No Structured Planning Process for the Business
    141 No Contingency or Scenario Planning
    142 No Systematic Way to Identify Business Risks
  All three are about whether the founder THINKS in plans, assumptions and
  risks -- answerable with nothing built. Left behind at Stage 0->1 on
  purpose: 140 (milestones), 151 (planning never shared -- needs an audience),
  152 (resource planning -- needs resources), 143/144/153/154 (mitigation,
  single points of failure, compliance review, risk ownership -- all need an
  operating business). Business Planning keeps 18 questions and Risk
  Identification 24 at Stage 0->1.

OUT (Stage 0 -> Stage 0->1), specific questions, 8:
  The fundraising-mechanics and compliance/governance questions listed above.
  Stage 0->1 is where they belong -- a founder with early traction raising a
  seed round genuinely does face valuation and data-privacy questions.

Net: Strategic Clarity at Stage 0 goes from 8 unanswerable questions across 2
categories to 20 answerable ones across 2 categories. Stage 0->1 nets 71,
still four categories.

INVERSE PRECISION. The two halves need different GRAIN:
  * BPL-001/BPL-003/RSK-001 have questions in Stage 0->1 ONLY, so the IN half
    can move a whole problem and its inverse is exact.
  * The fundraising/compliance problems have questions spread across ALL THREE
    groups, so the OUT half must NOT move a whole problem -- that would drag
    their unrelated Stage 0->1 and Stage 1->10+ questions along and the
    downgrade would over-restore. It keys on eight individual questions.

KEYING. Both halves match on business codes (`problems.problem_code`,
`questions.question_code`), never on serial ids. The ids were read off a
development copy of the catalogue; this migration also runs against production
RDS, which sits in a private VPC and cannot be inspected from a developer
machine beforehand. A mismatched id would silently re-tag the WRONG questions
and nothing would look broken. Both code columns are verified unique, so this
migration is either exactly right or matches nothing.
"""

from alembic import op
import sqlalchemy as sa

revision = "a91f4c76b2d8"
down_revision = "f6d2a81c53e7"
branch_labels = None
depends_on = None

_S0 = "Stage 0"
_S01 = "Stage 0→1"

#: Whole problems that belong at Stage 0 -- planning/assumption/risk THINKING,
#: answerable with nothing built. Keyed by problem_code, not problem_id (see
#: the KEYING note in the docstring).
_PROMOTE_PROBLEM_CODES = (
    "BPL-001",  # No Structured Planning Process for the Business
    "BPL-003",  # No Contingency or Scenario Planning
    "RSK-001",  # No Systematic Way to Identify Business Risks
)

#: Individual questions wrongly reachable at Stage 0 -- fundraising mechanics
#: and compliance/governance. Keyed at QUESTION grain, not problem grain: their
#: problems also hold Stage 0->1 and Stage 1->10+ questions that must not move.
_DEMOTE_QUESTION_CODES = (
    "FND-006",  # fundraising pitch built around evidence or personal conviction
    "FND-007",  # how did you arrive at your valuation
    "FND-013",  # who do you want as investors
    "FND-015",  # letters of intent or term sheets already
    "FND-020",  # warm investor relationships before pitching
    "OPS-006",  # data privacy comfort vs what is actually needed
    "OPS-012",  # backups and disaster recovery vs own risk tolerance
    "OPS-018",  # personally reviewing contracts is sufficient
)

_PROMOTE_SQL = (
    "update questions q set primary_stage_group = :to, updated_at = now() "
    "from problems p "
    "where p.problem_id = q.problem_id "
    "  and p.problem_code = any(:codes) "
    "  and q.primary_stage_group = :frm"
)

_DEMOTE_SQL = (
    "update questions set primary_stage_group = :to, updated_at = now() "
    "where question_code = any(:codes) and primary_stage_group = :frm"
)


def upgrade() -> None:
    bind = op.get_bind()

    promoted = bind.execute(
        sa.text(_PROMOTE_SQL),
        {"to": _S0, "frm": _S01, "codes": list(_PROMOTE_PROBLEM_CODES)},
    ).rowcount

    demoted = bind.execute(
        sa.text(_DEMOTE_SQL),
        {"to": _S01, "frm": _S0, "codes": list(_DEMOTE_QUESTION_CODES)},
    ).rowcount

    # Idempotent both ways: a re-run matches nothing, since each half filters
    # on the group it is moving FROM.
    print(f"INFO  Strategic Clarity: promoted {promoted} to {_S0}, "
          f"demoted {demoted} to {_S01}")


def downgrade() -> None:
    bind = op.get_bind()

    restored_up = bind.execute(
        sa.text(_DEMOTE_SQL),
        {"to": _S0, "frm": _S01, "codes": list(_DEMOTE_QUESTION_CODES)},
    ).rowcount

    restored_down = bind.execute(
        sa.text(_PROMOTE_SQL),
        {"to": _S01, "frm": _S0, "codes": list(_PROMOTE_PROBLEM_CODES)},
    ).rowcount

    print(f"INFO  Strategic Clarity restored: {restored_up} to {_S0}, "
          f"{restored_down} to {_S01}")
