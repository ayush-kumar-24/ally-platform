"""Give a DPDP grievance somewhere to land.

WHAT WAS THERE BEFORE. The Privacy Policy names a Grievance Officer, publishes
a `mailto:privacy@goxl.in`, and promises acknowledgement within 48 hours and
resolution within 30 days. `privacy@goxl.in` appears nowhere in the backend.
There was no form, no table, no ticket type, no timer -- a complaint left the
founder's own mail client or it did not exist. Nothing could acknowledge within
48 hours because nothing knew a complaint had been made.

Section 13 of the DPDP Act requires a readily available grievance-redressal
mechanism. A published address with no receiving system behind it is thin, and
the SLA attached to it was measuring nothing.

WHY IT RIDES ON `privacy_requests` RATHER THAN A NEW TABLE. It is the same
shape as everything already there -- a founder asks, a human actions it, and the
record belongs in the same audit trail. It also means a grievance appears in the
admin review queue that already exists and is already read, rather than in a
second queue somebody would have to remember. A regulator asking "show me every
complaint and what you did about it" gets one table, not two.

THE 48-HOUR CLOCK IS NOT IN THE DATABASE. `due_by` is set by an existing trigger
to the 30-day statutory window and is left alone. The shorter acknowledgement
target belongs to the screen a person reads: the admin queue sorts grievances
first and shows their age in hours. Encoding two different SLAs in one column
would make both harder to trust.

Revision ID: f1c8d3a26b47
Revises: e6b1a4c73d92
"""

from __future__ import annotations

from alembic import op

revision = "f1c8d3a26b47"
down_revision = "e6b1a4c73d92"
branch_labels = None
depends_on = None

_CONSTRAINT = "privacy_requests_request_type_check"

_NEW_TYPES = (
    "view_data", "download_data", "correct_data", "withdraw_consent",
    "restrict_processing", "portability", "delete_account", "cancel_deletion",
    "email_change", "grievance",
)
_OLD_TYPES = tuple(t for t in _NEW_TYPES if t != "grievance")


def _check_sql(types: tuple[str, ...]) -> str:
    values = ", ".join(f"'{t}'::character varying" for t in types)
    return f"request_type::text = ANY (ARRAY[{values}]::text[])"


def upgrade() -> None:
    op.drop_constraint(_CONSTRAINT, "privacy_requests", type_="check")
    op.create_check_constraint(_CONSTRAINT, "privacy_requests", _check_sql(_NEW_TYPES))


def downgrade() -> None:
    # A complaint is not a correction, but `correct_data` is the closest legal
    # value and losing the row entirely would be worse -- these are exactly the
    # records that must survive.
    op.execute(
        "update privacy_requests set request_type = 'correct_data' "
        "where request_type = 'grievance'"
    )
    op.drop_constraint(_CONSTRAINT, "privacy_requests", type_="check")
    op.create_check_constraint(_CONSTRAINT, "privacy_requests", _check_sql(_OLD_TYPES))
