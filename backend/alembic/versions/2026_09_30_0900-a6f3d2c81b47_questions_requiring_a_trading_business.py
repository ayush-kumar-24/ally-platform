"""questions: record which ones cannot be answered before the first sale.

THE DEFECT, found auditing the Validation bank the way the ideation one was
audited. Validation, Prototype/MVP and Early Traction share one question bank
and one set of rules, and nothing withholds a subject at any of them. So a
founder at Validation -- still testing whether anyone wants this, with no
customers and no revenue -- is a valid candidate for

    SAL-010   Have you hit your sales targets for the last quarter?
    FIN-014   How often is your profit and loss statement actually prepared?
    BMD-012   Last month, was your business profitable or just generating
              revenue?
    RSK-012   What percentage of your revenue comes from your single biggest
              customer?

They answer nothing, and `business_health` scores the blank as a gap -- so not
having launched reads back to them as weak finances. The same shape as the
team-size defect, on the money axis.

`founders.current_revenue` has been collected since onboarding was written,
including a `pre_revenue` band, and is shown on the founder brief. Nothing that
chooses questions has ever read it. This is the column that lets it.

A BOOLEAN, NOT A BAND, unlike `min_team_size`. Team size earned five levels
because the bank has real content at each -- questions needing a co-founder,
needing employees, needing managers, needing several departments. Revenue has
exactly one line in the evidence: trading or not. Nothing in the bank
distinguishes a founder at fifty thousand a month from one at five lakh. A
six-level scale we could not populate would be the fake precision this
repository keeps refusing elsewhere (see `50_plus` in b93f5c07d2e1). If a
second line ever shows up in the content, this becomes a band then.

HOW THE 160 WERE CHOSEN. A text rule over the whole bank, then read. The rule
requires a MONEY word, not merely a past period: an early version keyed on
"last month/quarter/year" alone and swept up "How many trainers have left in
the last year?" and "Where would someone read last year's programme numbers?",
which are about staff and about an NGO's reporting, not about trading. Two
further false positives were dropped by hand after reading every ideation-bank
match:

    IVA-077     "Do you believe targeting everyone actually maximizes your
                sales opportunities?" -- a belief about focus, answerable by
                someone who has never sold anything.
    S0-TRD-015  "If the exchange rate changed against you before payment, what
                would happen to your profit on the deal?" -- hypothetical.

"Your pricing" and "price list" were deliberately excluded from the rule. A
founder can have decided what to charge before charging anyone, and
`S0-SAS-305-1` "Is your pricing written down anywhere?" is a good pre-revenue
question -- it was opened to solo founders two migrations ago for the same
reason.

DELIBERATELY UNDER-INCLUSIVE. The audit's estimate was that 550 to 600
questions in the Validation bank presuppose trading; this tags 160. The gap is
questions whose wording implies it without naming money -- "What are the top
two or three objections prospects have when you send a proposal?". Tagging
those needs them read, which is a content pass, and
`scripts/review_question_trading.py` prints the worksheet. Under-tagging costs
an off-key question; over-tagging withholds one the founder could have
answered, and this bank is the only one they have.

Revision ID: a6f3d2c81b47
Revises: e4c9b21d8a76
Create Date: 2026-09-30 09:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a6f3d2c81b47"
down_revision: Union[str, Sequence[str], None] = "e4c9b21d8a76"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_COLUMN = "requires_trading"
_INDEX = "idx_questions_requires_trading"

#: Questions that name money already changing hands. Listed rather than
#: re-derived at migration time, so what was tagged is auditable in the diff
#: and cannot quietly change when the text does.
_REQUIRES_TRADING: tuple[str, ...] = (
    'BMD-005', 'BMD-012', 'BMD-033', 'FIN-004', 'FIN-012', 'FIN-014',
    'FIN-015', 'FIN-074', 'FIN-077', 'FIN-079', 'FIN-082', 'FIN-083',
    'FIN-152', 'FIN-162', 'FIN-164', 'FIN-199', 'FIN-202', 'FIN-204',
    'FIN-217', 'GTM-018', 'MEX-069', 'MEX-083', 'MEX-171', 'OPS-114',
    'RSK-012', 'S0-BPC-101-1', 'S01-BPC-105-2', 'S01-BPC-201-1',
    'S01-DLV-018', 'S01-DLV-307-1', 'S01-ECM-009', 'S01-FSH-015',
    'S01-GTM-011', 'S01-GTM-050', 'S01-HRT-302-1', 'S01-HRT-305-1',
    'S01-LGL-001', 'S01-LGL-307-2', 'S01-LOG-307-1', 'S01-PRD-030',
    'S01-RTL-013', 'S01-SAL-027', 'S01-SAL-034', 'S01-SLX-017',
    'S01-SLX-020', 'S01-SLX-021', 'S01-SLX-024', 'S01-SLX-025',
    'S01-SLX-028', 'S01-SVC-010', 'S01-TEL-009', 'S01-TEL-307-1',
    'S01-TXT-008', 'S10-AGR-023', 'S10-BPC-006', 'S10-BPC-014',
    'S10-CEL-019', 'S10-DLV-001', 'S10-ECM-010', 'S10-ECM-011',
    'S10-ECM-015', 'S10-ECM-017', 'S10-ENR-024', 'S10-FIN-055',
    'S10-FNB-021', 'S10-FSH-002', 'S10-GAM-001', 'S10-GTM-013',
    'S10-GTM-023', 'S10-GTM-028', 'S10-GTM-067', 'S10-HRT-302-2',
    'S10-LOG-024', 'S10-MEX-048', 'S10-MEX-086', 'S10-MKT-001',
    'S10-PHM-001', 'S10-PHM-007', 'S10-RTL-001', 'S10-RTL-010',
    'S10-RTL-018', 'S10-RTL-019', 'S10-SAL-002', 'S10-SAL-008',
    'S10-SAL-009', 'S10-SAL-014', 'S10-SAL-015', 'S10-SAL-016',
    'S10-SAL-019', 'S10-SAL-021', 'S10-SAL-023', 'S10-SAL-027',
    'S10-SAL-028', 'S10-SAL-031', 'S10-SAS-019', 'S10-SLX-031',
    'S10-SLX-032', 'S10-SLX-033', 'S10-SLX-034', 'S10-SLX-035',
    'S10-SLX-036', 'S10-SLX-044', 'S10-SLX-052', 'S10-SLX-065',
    'S10-SLX-073', 'S10-SLX-084', 'S10-SLX-086', 'S10-SPF-001',
    'S10-SPF-023', 'S10-SPF-307-2', 'S10-SVC-001', 'S10-SVC-302-1',
    'S10-TEL-001', 'S10-TRD-005', 'S10-TRD-006', 'S10-TRD-011',
    'S10-TRV-011', 'S10-TXT-001', 'SAL-001', 'SAL-003', 'SAL-007',
    'SAL-010', 'SAL-011', 'SAL-013', 'SAL-014', 'SAL-019', 'SAL-021',
    'SAL-024', 'SAL-030', 'SAL-040', 'SAL-044', 'SAL-065', 'SCL-099',
    'SCL-106', 'SCL-111', 'SCL-119', 'SCL-121', 'SCL-124', 'SCL-125',
    'SCL-126', 'SCL-128', 'SCL-129', 'SCL-137', 'SCL-195', 'SLX-022',
    'SLX-025', 'SLX-028', 'SLX-029', 'SLX-120', 'SLX-123', 'SLX-128',
    'SLX-129', 'SLX-130', 'SLX-133', 'SLX-213', 'SLX-214', 'SLX-279',
    'SLX-287', 'SLX-288', 'SLX-299'
)


def upgrade() -> None:
    bind = op.get_bind()

    op.add_column(
        "questions",
        sa.Column(_COLUMN, sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    # The rows that carry True are a small minority, so the index only covers
    # them -- same shape as idx_questions_min_team_size.
    op.create_index(
        _INDEX, "questions", [_COLUMN], postgresql_where=sa.text(_COLUMN),
    )

    tagged = bind.execute(
        sa.text(f"UPDATE questions SET {_COLUMN} = true WHERE question_code = ANY(:codes)"),
        {"codes": list(_REQUIRES_TRADING)},
    ).rowcount
    print(f"[{revision}] {tagged} of {len(_REQUIRES_TRADING)} questions need a "
          "trading business")
    if tagged != len(_REQUIRES_TRADING):
        missing = bind.execute(
            sa.text(
                "SELECT c FROM unnest(CAST(:codes AS text[])) AS c "
                "WHERE c NOT IN (SELECT question_code FROM questions)"
            ),
            {"codes": list(_REQUIRES_TRADING)},
        ).scalars().all()
        print(f"[{revision}] WARNING not in this database: {sorted(missing)}")

    for group, n in bind.execute(
        sa.text(
            f"SELECT primary_stage_group, count(*) FROM questions "
            f"WHERE {_COLUMN} GROUP BY 1 ORDER BY 1"
        )
    ).all():
        print(f"[{revision}]   {group}: {n}")


def downgrade() -> None:
    op.drop_index(_INDEX, table_name="questions")
    op.drop_column("questions", _COLUMN)
