"""Let a founder ask us to change the email address on their account.

THE HOLE THIS CLOSES. Email is set once, by the auth provider, at signup, and
the profile screen renders it read-only because we cannot persist a change. A
founder who mistypes it -- `gmial.com`, a missing letter, the wrong one of two
addresses -- ends up signed in as an address they do not own. Everything we send
them goes somewhere else: login codes, discovery-call confirmations, the report
share link. And the one channel we tell them to use when something is wrong
("email us from the address on your account") is the exact thing they cannot do.

They are locked out of correcting the mistake by the mistake itself.

WHY A QUEUED REQUEST AND NOT A SETTING. Changing the address on an account is
an account-takeover primitive: anyone who reaches an open session could point
the account at their own inbox and then use password reset to own it outright.
So this goes on the same admin review queue as a correction request, and a human
verifies who is asking before anything moves. That is also the honest answer
technically -- the address lives with the auth provider, not in a column we can
update from here.

WHY IT REUSES `privacy_requests`. It is the same shape as `correct_data`: a
founder asks, a human actions it within the same window, and the record belongs
in the same audit trail. A regulator asking "show me every correction this
founder requested" should not have to know we filed one class of correction in
a different table.

Revision ID: b4e7d21a9c68
Revises: c8e3a41f7b52
"""

from __future__ import annotations

from alembic import op

revision = "b4e7d21a9c68"
down_revision = "c8e3a41f7b52"
branch_labels = None
depends_on = None

_CONSTRAINT = "privacy_requests_request_type_check"

#: The eight f2c7a91d4e83 settled on, plus the one this migration adds.
_NEW_TYPES = (
    "view_data",
    "download_data",
    "correct_data",
    "withdraw_consent",
    "restrict_processing",
    "portability",
    "delete_account",
    "cancel_deletion",
    "email_change",
)

_OLD_TYPES = tuple(t for t in _NEW_TYPES if t != "email_change")


def _check_sql(types: tuple[str, ...]) -> str:
    values = ", ".join(f"'{t}'::character varying" for t in types)
    return f"request_type::text = ANY (ARRAY[{values}]::text[])"


def upgrade() -> None:
    op.drop_constraint(_CONSTRAINT, "privacy_requests", type_="check")
    op.create_check_constraint(_CONSTRAINT, "privacy_requests", _check_sql(_NEW_TYPES))


def downgrade() -> None:
    # Rows must be dealt with before the narrower constraint goes back on, or
    # the CREATE fails on existing data. `correct_data` is the honest home for
    # them: an email change IS a correction, and the address the founder gave us
    # is in request_details either way, so nothing an admin needs is lost.
    op.execute(
        """
        update privacy_requests
           set request_type = 'correct_data'
         where request_type = 'email_change'
        """
    )
    op.drop_constraint(_CONSTRAINT, "privacy_requests", type_="check")
    op.create_check_constraint(_CONSTRAINT, "privacy_requests", _check_sql(_OLD_TYPES))
