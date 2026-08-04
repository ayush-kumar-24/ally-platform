"""customer_segment becomes a multi-select list

Onboarding asks "Who are you building this for?" as chips, so a founder can be
building for Businesses *and* Developers *and* Enterprises at once. The column
was varchar(30), which could only hold one of those.

Existing scalar values are preserved by wrapping each into a single-element
array, so nothing is lost going forward. The free text behind the "Other" chip
continues to live in customer_segment_other.

Revision ID: e8f0a2c4d6b9
Revises: d269304c2e60
Create Date: 2026-08-04 11:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'e8f0a2c4d6b9'
down_revision: Union[str, Sequence[str], None] = 'd269304c2e60'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE founders
            ALTER COLUMN customer_segment TYPE jsonb
            USING CASE
                WHEN customer_segment IS NULL THEN NULL
                WHEN btrim(customer_segment) = '' THEN '[]'::jsonb
                ELSE to_jsonb(ARRAY[btrim(customer_segment)])
            END
        """
    )
    op.execute("ALTER TABLE founders ALTER COLUMN customer_segment SET DEFAULT '[]'::jsonb")


def downgrade() -> None:
    """Lossy by nature: a founder who picked several segments keeps only the
    first, because the varchar column cannot represent the rest."""
    op.execute("ALTER TABLE founders ALTER COLUMN customer_segment DROP DEFAULT")
    op.execute(
        """
        ALTER TABLE founders
            ALTER COLUMN customer_segment TYPE varchar(30)
            USING CASE
                WHEN customer_segment IS NULL THEN NULL
                WHEN jsonb_typeof(customer_segment) = 'array'
                     AND jsonb_array_length(customer_segment) > 0
                    THEN left(customer_segment ->> 0, 30)
                ELSE NULL
            END
        """
    )
