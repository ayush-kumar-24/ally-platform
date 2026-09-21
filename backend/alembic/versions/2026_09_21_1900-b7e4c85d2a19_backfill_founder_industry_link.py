"""backfill founders.industry_mapped_id from the industry name

Revision ID: b7e4c85d2a19
Revises: a3f7d92c1e58
Create Date: 2026-09-21

founders.industry (free text) and founders.industry_mapped_id (FK to
industries) have coexisted since the table was created, and nothing in the
running application has ever written the FK -- the only code that could was an
RDS function, complete_onboarding, which the app stopped calling. So it is NULL
for every founder.

That column is not decoration. The diagnosis engine, the reasoning service and
the Ally context builder all read it to choose an industry's dataset, so thirty
industries' worth of seeded problems, root causes, question banks and
interventions have been unreachable and every founder has been served the
generic bank regardless of what they do.

FounderRepository.update() now keeps the two in step on every write, but that
only helps a founder who saves their profile again. This links the founders who
are already here.

Matching is exact (case- and whitespace-insensitive) on industry_name or
industry_code, which is the same rule resolve_industry_id applies, so a founder
linked here and a founder linked at save time can never disagree.

Deliberately conservative -- no fuzzy matching:
  - only rows where industry_mapped_id IS NULL are touched, so anything set by
    hand is left alone;
  - a founder whose stored industry does not match stays NULL rather than being
    guessed into the nearest-looking industry. Onboarding offered twelve
    one-word industries before this week ('AI', 'D2C', 'Healthcare',
    'Education', 'Real Estate', 'Agriculture'), and those are genuinely
    ambiguous against the thirty real ones. Guessing would quietly feed a
    founder someone else's diagnosis content, which is worse than the generic
    bank they get today. Five of the old twelve do match a real industry_code
    exactly ('SaaS', 'Fintech', 'Manufacturing', 'Logistics', 'Services') and
    are linked; the rest are correctly left for the founder to re-answer.

The downgrade cannot distinguish the rows it filled from rows filled any other
way, so it deliberately does nothing rather than NULLing a column it does not
own. Nothing breaks by leaving the links in place: before this migration the
value was unused, and after a downgrade it is unused again.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "b7e4c85d2a19"
down_revision: Union[str, Sequence[str], None] = "a3f7d92c1e58"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE founders AS f
           SET industry_mapped_id = i.industry_id
          FROM industries AS i
         WHERE f.industry_mapped_id IS NULL
           AND f.industry IS NOT NULL
           AND btrim(f.industry) <> ''
           AND (
                 lower(btrim(f.industry)) = lower(i.industry_name)
              OR lower(btrim(f.industry)) = lower(i.industry_code)
               )
        """
    )


def downgrade() -> None:
    """Intentionally a no-op -- see the module docstring."""
