"""Record where a consent came from.

WHY

Under GDPR Art 7(1) and the DPDP Act a controller must be able to DEMONSTRATE
consent, not merely assert it. The ledger already answers what was agreed, to
which document version, and when. It could not answer where from -- and the
admin panel had no way to show it, so a compliance question could only be
answered by trusting the row.

Both columns are nullable with no default. Every consent recorded before today
genuinely has no address, and a sentinel ("0.0.0.0", "") would read as one --
"not recorded" and "recorded as unknown" are different claims, and only the
first is true of those rows.

The legacy `consents` and `consent_history` tables already carry ip_address
varchar(45); these match that width, which is sized for a full IPv6 address.

EVIDENCE, NOT IDENTITY. Nothing authorizes on these columns. They are written
from X-Forwarded-For, which is client-controllable -- see app/api/deps.py's
client_ip, which says the same thing where it is easier to find.

Additive and nullable, so an older container serving traffic during a rollout
neither sees nor writes them.

Revision ID: c5e1a83b642d
Revises: b4d9e2a71f38
"""

from alembic import op
import sqlalchemy as sa

revision = "c5e1a83b642d"
down_revision = "b4d9e2a71f38"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("founder_consents", sa.Column("ip_address", sa.String(length=45), nullable=True))
    op.add_column("cookie_preferences", sa.Column("ip_address", sa.String(length=45), nullable=True))


def downgrade() -> None:
    op.drop_column("cookie_preferences", "ip_address")
    op.drop_column("founder_consents", "ip_address")
