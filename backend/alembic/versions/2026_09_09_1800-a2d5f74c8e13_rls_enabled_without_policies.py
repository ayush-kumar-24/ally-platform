"""Give the tables that had RLS switched on the policies that were never created.

PRODUCTION OUTAGE, ROOT CAUSE. Sign-up died at POST /auth/session with

    psycopg2.errors.InsufficientPrivilege: new row violates row-level
    security policy for table "waitlist_registrations"

Four migrations (b8e3d5a91c47 waitlist_registrations, a4d7c6e2b915
waitlist_slot_openings, c8f3a92e1d47 direct_signup_capacity, e5b2d47a91c3
launch_state) are all written to the same shape:

    op.execute('ALTER TABLE ... ENABLE ROW LEVEL SECURITY')   # unconditional
    if _ally_app_exists():
        op.execute('CREATE POLICY ...')                       # conditional
        op.execute('GRANT ... TO ally_app')                   # conditional

The guard exists because local and CI databases have no `ally_app` role and
CREATE POLICY ... TO a missing role is an error. But only the policy is behind
it. Enabling RLS is not. So in any database without that role -- which is what
the failing environment turned out to be -- the table ends up with row level
security ON and NOT ONE POLICY, and Postgres denies by default:

  * every INSERT/UPDATE fails with the error above, and
  * every SELECT quietly returns zero rows, with no error at all.

That second half is why this hid for so long. The admin panel's waitlist read
"0 of 300 places taken - Nothing waiting" and looked like an empty queue rather
than an unreadable table, and the public registration form had never once
managed to write a row. The count really was zero, because nothing could ever
be inserted.

THE FIX, AND WHY IT IS NOT "ADD THE ROLE TO THE GUARD"
Policies are not privileges. A policy decides which rows a role may see or
write ONCE it already holds table-level GRANTs; it never hands out access on
its own. So these policies are created FOR PUBLIC here rather than for one
named role, which makes them correct in every environment regardless of which
role the application connects as -- and costs nothing in security, because the
boundary that actually keeps PostgREST's `anon`/`authenticated` out of these
tables is the absence of a GRANT, which this migration does not change and
explicitly re-asserts below.

WHY `USING (true)` AND NOT THE ORIGINAL ADMIN GATE
b8e3d5a91c47 wrote `USING (app.current_admin) WITH CHECK (true)`, reasoning
that only an admin should read the queue while the public form still inserts.
That combination cannot work for this table's own writer: services/waitlist.py
::register() inserts with `RETURNING registration_id`, and Postgres applies the
SELECT side of the policy to rows a RETURNING clause hands back. With an
admin-only USING, the public form's insert would have gone on failing -- just
with a different message -- the moment the policy existed. The read
restriction it was reaching for is delivered by the GRANTs instead.

Idempotent, and safe to run against a database where the earlier migrations
DID create their policies: each one is dropped by name and recreated.
"""

from alembic import op
import sqlalchemy as sa

revision = "a2d5f74c8e13"
down_revision = "f6c3b58e2d94"
branch_labels = None
depends_on = None

_ADMIN = "COALESCE(NULLIF(current_setting('app.current_admin', true), '')::boolean, false)"

# table -> (policy name to install, USING expression, WITH CHECK expression)
#
# launch_state keeps its split: the gate's status endpoint is unauthenticated
# by design and must be readable by anyone the app serves, while only an admin
# context may move the state. Its read policy was already TO ally_app and is
# recreated here for PUBLIC on the same reasoning as the rest.
_TABLES = {
    "waitlist_registrations": [
        ("waitlist_registrations_app", "ALL", "true", "true"),
    ],
    "waitlist_slot_openings": [
        ("waitlist_slots_admin_only", "ALL", _ADMIN, _ADMIN),
    ],
    "direct_signup_capacity": [
        # Read by the public capacity endpoint; written by the capacity gate on
        # an ordinary sign-in, which carries no admin context -- so the write
        # side cannot demand one without breaking the thing it guards.
        ("direct_signup_capacity_app", "ALL", "true", "true"),
    ],
    "launch_state": [
        ("launch_state_readable", "SELECT", "true", None),
        ("launch_state_admin_writes", "UPDATE", _ADMIN, _ADMIN),
    ],
}

# Old policy names that may exist from the original migrations, dropped first
# so a re-run cannot leave two policies OR-ing together into something wider
# than either was meant to be.
_LEGACY = {
    "waitlist_registrations": ["waitlist_registrations_admin_only"],
    "waitlist_slot_openings": [],
    "direct_signup_capacity": ["direct_signup_capacity_admin_only"],
    "launch_state": [],
}


def _table_exists(name: str) -> bool:
    return bool(
        op.get_bind()
        .execute(sa.text("SELECT to_regclass(:n)"), {"n": f"public.{name}"})
        .scalar()
    )


def upgrade() -> None:
    for table, policies in _TABLES.items():
        if not _table_exists(table):
            continue

        # RLS may already be on (that is the bug) or off; assert it either way,
        # now that there will actually be policies to go with it.
        op.execute(f'ALTER TABLE public."{table}" ENABLE ROW LEVEL SECURITY')

        for name in _LEGACY[table] + [p[0] for p in policies]:
            op.execute(f'DROP POLICY IF EXISTS "{name}" ON public."{table}"')

        for name, command, using, with_check in policies:
            clauses = f"USING ({using})"
            if with_check is not None:
                clauses += f" WITH CHECK ({with_check})"
            op.execute(
                f'CREATE POLICY "{name}" ON public."{table}" '
                f"AS PERMISSIVE FOR {command} TO PUBLIC {clauses}"
            )

        # The real boundary. Restated rather than assumed: these tables hold
        # registration emails and the switch that opens the platform, and none
        # of it is a legitimate direct PostgREST read.
        op.execute(f'REVOKE ALL ON public."{table}" FROM anon, authenticated')


def downgrade() -> None:
    """Drops the policies but LEAVES RLS ENABLED, exactly as this migration
    found it. Restoring the broken state on purpose would put the outage back."""
    for table, policies in _TABLES.items():
        if not _table_exists(table):
            continue
        for name, *_ in policies:
            op.execute(f'DROP POLICY IF EXISTS "{name}" ON public."{table}"')
