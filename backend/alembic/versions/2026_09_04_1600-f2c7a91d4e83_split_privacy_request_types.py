"""Give erasure and its cancellation their own audit labels.

`privacy_requests.request_type` allowed six values, and none of them was
"the founder asked us to delete their account". So `request_account_deletion`,
`cancel_account_deletion` and `withdraw_consent` all wrote the same label:
`withdraw_consent`. Three materially different events -- one of them the most
consequential thing a founder can do -- were indistinguishable in the one table
whose entire purpose is to record who exercised which right and when.

The damage is not hypothetical. In production today, six rows carry
`withdraw_consent`: two are erasure requests, two are cancellations of those
erasures, and only two are actual consent withdrawals. A regulator asking "show
me every deletion request in the last year" could not be answered from this
table, and neither could "prove this founder cancelled".

`request_details` is what makes the history recoverable: the service has always
written a distinct sentence for each of the three, so the backfill below
reclassifies on that rather than guessing.

One class of row is deliberately NOT touched. Before the export split, both
Privacy Center download buttons called one endpoint and logged `portability`,
so the 20 rows reading "Self-service export downloaded" could have been either
right. They stay `portability`. Inventing a distinction the old code never
recorded would be worse than an honest ambiguity -- these are compliance
records, and a confident wrong answer in them is the failure mode that matters.

Revision ID: f2c7a91d4e83
Revises: a3f81c05e6d7
"""

from __future__ import annotations

from alembic import op

revision = "f2c7a91d4e83"
down_revision = "a3f81c05e6d7"
branch_labels = None
depends_on = None

_CONSTRAINT = "privacy_requests_request_type_check"

#: The six that existed, plus the two that should always have.
_NEW_TYPES = (
    "view_data",
    "download_data",
    "correct_data",
    "withdraw_consent",
    "restrict_processing",
    "portability",
    "delete_account",
    "cancel_deletion",
)

_OLD_TYPES = tuple(t for t in _NEW_TYPES if t not in ("delete_account", "cancel_deletion"))


def _check_sql(types: tuple[str, ...]) -> str:
    values = ", ".join(f"'{t}'::character varying" for t in types)
    return f"request_type::text = ANY (ARRAY[{values}]::text[])"


def upgrade() -> None:
    # Order matters: the backfill writes values the old constraint forbids, so
    # the constraint comes off first and the new one goes on last.
    op.drop_constraint(_CONSTRAINT, "privacy_requests", type_="check")

    # Erasure requests. The service has written this sentence since the feature
    # shipped; the date suffix varies, hence the prefix match.
    op.execute(
        """
        update privacy_requests
           set request_type = 'delete_account'
         where request_type = 'withdraw_consent'
           and request_details like 'Account erasure requested%'
        """
    )

    # Cancellations of those erasures.
    op.execute(
        """
        update privacy_requests
           set request_type = 'cancel_deletion'
         where request_type = 'withdraw_consent'
           and request_details like 'Account deletion cancelled%'
        """
    )

    op.create_check_constraint(_CONSTRAINT, "privacy_requests", _check_sql(_NEW_TYPES))


def downgrade() -> None:
    op.drop_constraint(_CONSTRAINT, "privacy_requests", type_="check")

    # Collapse the two new labels back into the one the old constraint allowed.
    # Lossy by nature -- that loss is the defect this migration exists to end --
    # but `request_details` still carries the distinction, so a re-upgrade
    # reclassifies exactly the same rows again.
    op.execute(
        """
        update privacy_requests
           set request_type = 'withdraw_consent'
         where request_type in ('delete_account', 'cancel_deletion')
        """
    )

    op.create_check_constraint(_CONSTRAINT, "privacy_requests", _check_sql(_OLD_TYPES))
