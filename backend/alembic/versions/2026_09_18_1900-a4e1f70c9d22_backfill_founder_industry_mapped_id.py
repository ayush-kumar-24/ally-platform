"""backfill founders.industry_mapped_id from the industry label

Revision ID: a4e1f70c9d22
Revises: d3e8b41c9a52
Create Date: 2026-09-18 19:00

`founders.industry` holds a dropdown LABEL; `industry_mapped_id` is the
catalogue key the reasoning context, the diagnosis session snapshot and the Ally
context builder all read. Nothing ever wrote it -- measured on production
2026-09-18, it was NULL for 46 of 47 founders -- so every industry-aware
decision downstream had no industry to work with.

`app/repositories/founder.py` now derives it on every profile write, which fixes
it going forward. This is the other half: the founders who onboarded before that
existed and will not touch their profile again.

WHAT IT TOUCHES. Only rows where `industry_mapped_id IS NULL`. A non-NULL
mapping is never overwritten -- if something else set it, that something knew
more than a label lookup does.

WHAT IT DELIBERATELY DOES NOT DO. It does not guess. A label with no entry in
the map below is left NULL and counted in the summary the migration prints. NULL
reads downstream as UNKNOWN and fails open; a wrong industry would filter that
founder's questions to somebody else's industry, which is worse than not knowing.

ROLLBACK. The upgrade records every founder_id it wrote into
`_industry_backfill_audit`, and the downgrade nulls exactly those rows and drops
the table. That is why the audit table exists rather than the downgrade
re-deriving the mapping: re-deriving cannot tell a row this migration set apart
from one set later by an ordinary profile edit, and would clear both.

NOT FOR PRODUCTION AS IT STANDS. Production's alembic_version reads
`f8a3c26e4b91`, a revision that is not on main, and the industry columns and
rows are present there without an alembic record. Reconciling that history is a
separate deployment task; this revision is written for repository-managed
environments and must not be the vehicle for fixing production's stamp.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "a4e1f70c9d22"
down_revision: Union[str, Sequence[str], None] = "d3e8b41c9a52"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

#: A SNAPSHOT of app/services/industry_mapping.INDUSTRY_LABEL_TO_CODE, inlined
#: on purpose. A migration is a record of what was done on the day it ran; if it
#: imported the live map, re-running this revision after a product decision
#: changed a mapping would silently write different data than it did the first
#: time. `test_industry_mapping.py` asserts the two agree today, so drift is
#: caught rather than assumed away.
#:
#: 'Other' is in the application map as an explicit None and is simply absent
#: here -- there is nothing to backfill it to.
_LABEL_TO_CODE = [
    ("ai", "saas"),
    ("saas", "saas"),
    ("fintech", "fintech"),
    ("manufacturing", "manufacturing"),
    ("healthcare", "healthtech"),
    ("education", "edtech"),
    ("d2c", "ecommerce_d2c"),
    ("services", "services"),
    ("logistics", "logistics"),
    ("real estate", "proptech"),
    ("agriculture", "agritech"),
]


def upgrade() -> None:
    bind = op.get_bind()

    bind.exec_driver_sql(
        "CREATE TABLE IF NOT EXISTS _industry_backfill_audit ("
        " founder_id integer PRIMARY KEY,"
        " backfilled_at timestamptz NOT NULL DEFAULT now())"
    )

    values = ", ".join(f"('{label}', '{code}')" for label, code in _LABEL_TO_CODE)

    # Pass 1 -- the onboarding dropdown labels.
    bind.exec_driver_sql(
        f"""
        WITH resolved AS (
            SELECT f.founder_id, i.industry_id
              FROM founders f
              JOIN (VALUES {values}) AS m(label, code)
                ON lower(btrim(f.industry)) = m.label
              JOIN industries i
                ON lower(i.industry_code) = m.code
             WHERE f.industry_mapped_id IS NULL
               AND f.industry IS NOT NULL
        ), updated AS (
            UPDATE founders f
               SET industry_mapped_id = r.industry_id
              FROM resolved r
             WHERE f.founder_id = r.founder_id
         RETURNING f.founder_id
        )
        INSERT INTO _industry_backfill_audit (founder_id)
        SELECT founder_id FROM updated
        ON CONFLICT (founder_id) DO NOTHING
        """
    )

    # Pass 2 -- rows whose `industry` already holds a catalogue code or name
    # rather than a dropdown label. Production has both shapes: 'saas' (a code)
    # and 'Technology & SaaS' (a name), alongside the labels.
    bind.exec_driver_sql(
        """
        WITH resolved AS (
            SELECT f.founder_id, i.industry_id
              FROM founders f
              JOIN industries i
                ON lower(i.industry_code) = lower(btrim(f.industry))
                OR lower(i.industry_name) = lower(btrim(f.industry))
             WHERE f.industry_mapped_id IS NULL
               AND f.industry IS NOT NULL
        ), updated AS (
            UPDATE founders f
               SET industry_mapped_id = r.industry_id
              FROM resolved r
             WHERE f.founder_id = r.founder_id
         RETURNING f.founder_id
        )
        INSERT INTO _industry_backfill_audit (founder_id)
        SELECT founder_id FROM updated
        ON CONFLICT (founder_id) DO NOTHING
        """
    )

    # Report, never fail. An unmapped label is a product question ("should the
    # dropdown offer this?"), not a reason to block a deployment.
    rows = bind.exec_driver_sql(
        "SELECT btrim(industry) AS label, count(*) AS founders"
        "  FROM founders"
        " WHERE industry IS NOT NULL AND btrim(industry) <> ''"
        "   AND industry_mapped_id IS NULL"
        " GROUP BY 1 ORDER BY 2 DESC"
    ).fetchall()
    mapped = bind.exec_driver_sql(
        "SELECT count(*) FROM _industry_backfill_audit"
    ).scalar()
    print(f"[a4e1f70c9d22] industry_mapped_id backfilled for {mapped} founder(s)")
    if rows:
        print("[a4e1f70c9d22] labels left unmapped (industry stays UNKNOWN, fails open):")
        for label, founders in rows:
            print(f"    {label!r}: {founders} founder(s)")


def downgrade() -> None:
    bind = op.get_bind()
    bind.exec_driver_sql(
        "UPDATE founders SET industry_mapped_id = NULL"
        " WHERE founder_id IN (SELECT founder_id FROM _industry_backfill_audit)"
    )
    bind.exec_driver_sql("DROP TABLE IF EXISTS _industry_backfill_audit")
