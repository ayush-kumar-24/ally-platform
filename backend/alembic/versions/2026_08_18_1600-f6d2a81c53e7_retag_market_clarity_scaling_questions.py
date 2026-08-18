"""Re-tag mis-stage-tagged Market Clarity questions to Stage 1->10+.

Found while fixing pillar coverage in the selection engine. Once the engine
started spreading the question budget across all six readiness pillars,
Market Clarity (pillar 2) turned out to have only FOUR questions a scaling
founder could reach, against 72-270 for every other pillar:

    pillar               Stage 0   Stage 0->1   Stage 1->10+
    P1 Founder Readiness      70          121             96
    P2 Market Clarity        105          252              4   <-- famine
    P3 Revenue Maturity       12          487            152
    P4 Product & Execution    10          151             72
    P5 Team & Leadership      10           93            131
    P6 Strategic Clarity       8           83            270

So a Stage 1->10+ founder's Market Clarity score was computed from at most 4
answers, all from one problem. That is a bank-tagging gap, not a selection
one.

This is a genuine mis-tag rather than a workaround. The questions under these
problems presuppose an operating business with customers, campaigns and a
team -- they cannot be answered by a Stage 0->1 founder at all:

    "Have you ever cut a channel from a campaign because you could show it
     wasn't contributing?"                                  (problem 219)
    "Among your current customers, are there clearly different types of
     people or use cases...?"                               (problem 145)

Selection is not the only consumer. `questions.primary_stage_group` also
feeds stage-detection corroboration (app/api/v1/reasoning/engines/
stage_detection.py, joined in reasoning/repository.py), so a scaling founder
answering these now corroborates the stage they actually declared instead of
contradicting it.

Deliberately a MOVE, not a widening to NULL (stage-agnostic). NULL means all
three groups, which would push campaign-attribution questions at idea-stage
founders -- the exact "don't let the founder default to needing more
marketing" bias the Stage-Adaptive doc's s5 warns against. Moving costs
Stage 0->1 nothing that matters: it keeps 118 Market Clarity questions and a
session asks about five per pillar.

CONSERVATIVE BY DESIGN. Only problems whose subject matter *requires* an
operating business are moved. Ambiguous marketing problems (content calendar,
planning horizon, landing pages, seasonal moments, competitive timing) stay
at Stage 0->1, as do all of Idea & Validation and the early discovery/persona
problems.

PRECONDITION for the exact inverse: none of these 18 problems currently has
any question tagged Stage 1->10+ (verified against production before
authoring), so downgrade() restoring them all to Stage 0->1 is lossless.
If that ever stops holding, downgrade() would over-restore -- it reverts by
(problem_code, current group) and cannot distinguish a row this migration moved
from one that was already there. Re-check before relying on the downgrade.

Keyed by problem_code rather than problem_id so it is safe to run against a
database whose serial ids differ from the one it was authored on. Verified
against production RDS is NOT possible from a laptop -- RDS sits in a private
VPC -- which is exactly why the id-based version was unacceptable.
"""

from alembic import op
import sqlalchemy as sa

revision = "f6d2a81c53e7"
down_revision = "e5c1a70d93b4"
branch_labels = None
depends_on = None

_FROM = "Stage 0→1"
_TO = "Stage 1→10+"

#: Problems whose questions presuppose an operating business at scale.
#:
#: Keyed by `problems.problem_code`, NOT by problem_id. The ids were read off a
#: development copy of the catalogue, and this migration also has to run
#: against production RDS, where a serial primary key carries no guarantee of
#: matching. Re-tagging by a mismatched id would silently move the WRONG
#: questions -- worse than failing, because nothing would look broken.
#: problem_code is the stable business key (verified unique), so this is
#: correct on any database or it matches nothing at all.
_SCALING_PROBLEM_CODES = (
    # Go-To-Market -- channel and positioning work never stops at scale
    "GTM-003",  # Wrong or Untested Channels
    "GTM-004",  # Poor Positioning and Messaging
    # Competitive Awareness -- an ongoing posture, not a one-off launch task
    "CMA-015",  # No Response Plan for Competitor Moves
    "CMA-020",  # No Clear Differentiation from Competitors
    "CMA-025",  # Competitor Strengths Never Studied for Learning
    # Target Customer & ICP -- segmentation needs a customer base to segment.
    # NOTE only TCI-011 moves. "Customer Understanding Not Updated as Product
    # Evolves" is deliberately LEFT at Stage 0->1: it and TCI-011 were the only
    # two ICP problems in that group, and moving both emptied Target Customer &
    # ICP for Stage 0->1 entirely -- a founder with early customers, actively
    # working out who they sell to, would have got no ICP question at all. It
    # also genuinely applies early, where the product changes fastest and
    # customer understanding goes stale quickest. This leaves ICP represented
    # on both sides (6 questions each).
    "TCI-011",  # No Segmentation Beyond a Single Customer Type
    # Marketing Execution -- campaign portfolio / team / measurement maturity
    "MEX-006",  # No Reusable System for Generating Marketing Content
    "MEX-016",  # No Structured Post-Campaign Analysis Process
    "MEX-046",  # No Defined Brand Voice or Style Guide for Content Creation
    "MEX-051",  # No Visual or Media Asset System to Support Content Creation
    "MEX-056",  # No Editing or Quality Review Step Before Content Gets Published
    "MEX-066",  # No Coordination With Sales or Fulfillment Before a Campaign
    "MEX-071",  # No Small-Scale Test Before Committing Full Campaign Budget
    "MEX-081",  # No Calculation of Campaign ROI or Cost-Efficiency
    "MEX-086",  # No Channel-Level Attribution Within a Multi-Channel Campaign
    "MEX-091",  # No Audience Segment-Level Analysis of Campaign Performance
    "MEX-096",  # No Post-Campaign Analysis of Which Message or Creative Worked
    "MEX-101",  # No Sharing of Campaign Results or Learnings With the Team
)

_MOVE_SQL = (
    "update questions q set primary_stage_group = :to, updated_at = now() "
    "from problems p "
    "where p.problem_id = q.problem_id "
    "  and p.problem_code = any(:codes) "
    "  and q.primary_stage_group = :frm"
)


def upgrade() -> None:
    result = op.get_bind().execute(
        sa.text(_MOVE_SQL),
        {"to": _TO, "frm": _FROM, "codes": list(_SCALING_PROBLEM_CODES)},
    )
    # Idempotent: a re-run matches nothing because the rows are already _TO.
    print(f"INFO  retagged {result.rowcount} Market Clarity questions to {_TO}")


def downgrade() -> None:
    result = op.get_bind().execute(
        sa.text(_MOVE_SQL),
        {"to": _FROM, "frm": _TO, "codes": list(_SCALING_PROBLEM_CODES)},
    )
    print(f"INFO  restored {result.rowcount} Market Clarity questions to {_FROM}")
