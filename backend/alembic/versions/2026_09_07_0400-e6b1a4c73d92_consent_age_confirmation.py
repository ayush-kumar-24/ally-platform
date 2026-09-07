"""Record that the founder confirmed they are 18 or over.

WHY THIS IS NOT JUST A LINE IN THE TERMS. The Terms of Service already say "you
confirm that you are at least 18 years old" -- and nothing anywhere collected,
checked or stored that confirmation. No date of birth, no checkbox, no column.
The only evidence of an age assurance was a sentence in a document nobody is
required to read.

Under India's DPDP Act, processing a child's personal data requires verifiable
parental consent, and s.9(3) additionally forbids tracking and targeted
advertising directed at children. That section carries the Act's highest penalty
band. A self-declaration checkbox is not verification and does not pretend to be
-- but it is the difference between an unevidenced sentence in a contract and a
dated, stored attestation the founder actively made, which is the ordinary
standard for a B2B product of this kind.

WHY IT LIVES ON THE CONSENT LEDGER rather than on `founders`. This is an
assertion made at a moment in time, against a specific version of the terms, and
the consent ledger is already exactly that: append-only, server-stamped,
version-tagged. Putting it on `founders` would make it a mutable field with no
record of when it was given -- which is the property that makes it worth having.

NULLABLE, NOT DEFAULT-FALSE, for existing rows. Founders who signed up before
this column existed were never asked. Recording them as `false` would assert
they declined; recording them as `true` would fabricate an attestation they
never made. NULL is the honest value: "not asked". New consents always carry a
real boolean.

Revision ID: e6b1a4c73d92
Revises: d3f8b71c02a9
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "e6b1a4c73d92"
down_revision = "d3f8b71c02a9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "founder_consents",
        sa.Column("age_confirmed", sa.Boolean(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("founder_consents", "age_confirmed")
