"""widen founders.industry for the real industry taxonomy

Revision ID: a3f7d92c1e58
Revises: f1e53a6b8c04
Create Date: 2026-09-21

founders.industry has been VARCHAR(30) since the table was written, when
onboarding offered twelve one-word industries ('AI', 'SaaS', 'D2C'). It now
offers the thirty the product actually has diagnostic content for -- the
industries.industry_name values seeded by the batch A-E migrations -- and eight
of those thirty are longer than thirty characters:

    Construction & Real Estate / PropTech      37
    Professional Services & Consulting *       34
    Healthcare & HealthTech / MedTech          33
    Marketing, Advertising & AdTech            31
    Non-Profit, Social Impact & NGO            31

(* stored as 'Services & Consulting'; the label is what the founder searches.)

Without this the founder picks one, the PATCH is refused 422 by the length
bound on BusinessInfoUpdate.industry, and the answer is silently lost at the
one point in onboarding where they cannot tell anything went wrong.

100, matching industries.industry_name, rather than a round number of its own:
the two hold the same strings and a column that can hold one but not the other
is the bug this is fixing, one size up.

Widening a varchar is a catalog-only change in PostgreSQL -- no table rewrite,
no lock beyond ACCESS EXCLUSIVE for the duration of the catalog update -- so
this is safe on a live founders table.

The downgrade truncates: any value longer than 30 characters would otherwise
fail the narrowing. It keeps the first 30 rather than refusing, because a
rollback that cannot run is not a rollback -- but a downgrade past this point
does lose the tail of those industry names, which is why it says so here.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "a3f7d92c1e58"
down_revision: Union[str, Sequence[str], None] = "f1e53a6b8c04"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "founders",
        "industry",
        existing_type=sa.String(length=30),
        type_=sa.String(length=100),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.execute(
        "UPDATE founders SET industry = left(industry, 30) "
        "WHERE industry IS NOT NULL AND char_length(industry) > 30"
    )
    op.alter_column(
        "founders",
        "industry",
        existing_type=sa.String(length=100),
        type_=sa.String(length=30),
        existing_nullable=True,
    )
