"""row level security on the five tables that had none

Revision ID: c9f41b8e3a07
Revises: b7e4c85d2a19

Supabase's own advisor flagged these: every other table in the schema has RLS
enabled, and these five did not. RLS off means the `anon` role -- the key that
ships inside every browser that loads the app -- can read AND write every row.

Two of them hold founder data outright:

  support_bot_misses    founder_id + the question the founder actually typed,
                        i.e. a log of what founders asked that Ally could not
                        answer. Personal data by any reading. It does NOT get
                        the ordinary founder-isolation policy -- see the note
                        on MISS_TABLE below, which is the one genuinely
                        interesting decision in this migration.
  coupon_redemptions    founder_id + coupon + payment + discount. Personal,
                        and financial.

The other three are not personal, and the risk on them is WRITE, not read:

  coupons               anyone holding the anon key could mint themselves a
                        100%-off code, or read every code we have issued.
  support_bot_answers   the help content founders are shown. Anyone could
                        rewrite what Ally tells them.
  notification_types    the notification catalogue. Config, but config that
                        nobody outside should be able to edit.

WHY THIS IS SAFE TO APPLY, on both targets, which is the question that matters
because enabling RLS without a matching policy is how you take an application
down:

  On RDS the `ally_app` role exists and is subject to RLS, so every table below
  gets an explicit policy for it -- founder isolation for the two founder
  tables, matching d91c6e4b72aa exactly, and unrestricted for the three global
  ones, which is what the app already had.

  On Supabase `ally_app` does not exist (see f2f3d7d7ce11) and the app connects
  as `postgres`, which carries rolbypassrls -- verified live, not assumed. So
  RLS is enabled with no policy at all: the app is unaffected, and anon and
  authenticated are denied, which is the entire point.

  Nothing in the frontend queries these tables through Supabase. It uses
  Supabase for AUTH only; every read goes through the backend. So there is no
  browser code that loses access here.

NOT INCLUDED: `_perf_baseline`, which the advisor also flagged. It is not in
this schema -- no migration creates it and no application code reads it. It is
a pg_stat_statements dump left behind by the query-performance work, and its
`q` column holds raw query text. Securing a stray artifact is the wrong fix;
it should be dropped. See backend/docs/RLS-REMEDIATION.md.
"""

from alembic import op
from sqlalchemy import text


revision = "c9f41b8e3a07"
down_revision = "b7e4c85d2a19"
branch_labels = None
depends_on = None


ALLY_APP_ROLE = "ally_app"

#: Same policy name as d91c6e4b72aa, because for the two founder tables this IS
#: that policy -- they were simply missed when it was written.
FOUNDER_POLICY = "ally_founder_isolation"
#: A separate name, so the two intents are never confused by someone reading
#: pg_policies: this one deliberately does NOT restrict rows.
GLOBAL_POLICY = "ally_app_global_read_write"

#: founder_id-scoped, and genuinely so: every write carries a real founder and
#: the only read is an admin listing, which the predicate's admin branch covers.
FOUNDER_TABLES = ("coupon_redemptions",)

#: Not founder-scoped. The app needs all rows; anon needs none.
GLOBAL_TABLES = ("coupons", "support_bot_answers", "notification_types")

#: support_bot_misses is neither, and a plain founder-isolation policy on it
#: would be quietly WRONG in both directions.
#:
#: WRITE: the PUBLIC support route answers people who are not signed in and
#: passes `founder_id=0` as a sentinel (api/v1/support/public.py). Against
#: `founder_id = public.get_founder_id()` that insert is refused -- and
#: SupportMissRepository.record swallows every failure by design, because it
#: runs on the path where a founder is already being told we have no answer.
#: So the policy would not break anything visibly; it would silently stop
#: recording public misses, which is the worst kind of change to make.
#:
#: READ: nothing in the application reads this table at all. It is written by
#: the bot and queried by hand when someone asks what founders are stuck on.
#:
#: So the two operations get two policies: anyone the app authorises may
#: INSERT, and only an admin context may SELECT. That is stricter than the
#: founder predicate on reads and correct on writes, where the founder
#: predicate is simply false.
MISS_TABLE = "support_bot_misses"
MISS_INSERT_POLICY = "ally_app_miss_insert"
MISS_READ_POLICY = "ally_app_miss_admin_read"


def _ally_app_exists() -> bool:
    """Whether the RDS-only `ally_app` runtime role exists on this target.
    Duplicated per-migration on purpose -- see the note in 7c4f0f1a9d2e."""
    return bool(
        op.get_bind()
        .execute(text("SELECT 1 FROM pg_roles WHERE rolname = :role"),
                 {"role": ALLY_APP_ROLE})
        .scalar()
    )


def _table_exists(table: str) -> bool:
    """A table named here may not exist on every target. Skipping is correct;
    aborting `alembic upgrade head` is not, because the Dockerfile runs it on
    container start and a failure there blocks the deploy."""
    return bool(
        op.get_bind()
        .execute(text("SELECT to_regclass(:name)"), {"name": f"public.{table}"})
        .scalar()
    )


def _predicate(column: str = "founder_id") -> str:
    """Byte-for-byte the predicate d91c6e4b72aa uses. These two tables belong to
    that set and were omitted from it; they should not acquire a second, subtly
    different definition of the same rule."""
    admin = ("COALESCE(NULLIF(current_setting('app.current_admin', true), '')"
             "::boolean, false)")
    return f"({column} = public.get_founder_id()) OR ({admin})"


def upgrade() -> None:
    has_role = _ally_app_exists()
    if not has_role:
        print("[c9f41b8e3a07] ally_app absent (Supabase target): enabling RLS "
              "with no policies. The app connects as a BYPASSRLS role, so it "
              "is unaffected; anon and authenticated are denied, which is the "
              "purpose of this migration.")

    for table in FOUNDER_TABLES + GLOBAL_TABLES + (MISS_TABLE,):
        if not _table_exists(table):
            print(f"[c9f41b8e3a07] {table} absent on this target, skipped")
            continue

        op.execute(f'ALTER TABLE public."{table}" ENABLE ROW LEVEL SECURITY')
        if not has_role:
            continue

        if table == MISS_TABLE:
            admin = ("COALESCE(NULLIF(current_setting('app.current_admin', true), '')"
                     "::boolean, false)")
            op.execute(f'DROP POLICY IF EXISTS "{MISS_INSERT_POLICY}" ON public."{table}"')
            op.execute(
                f'CREATE POLICY "{MISS_INSERT_POLICY}" ON public."{table}" '
                f"AS PERMISSIVE FOR INSERT TO {ALLY_APP_ROLE} "
                "WITH CHECK (true)"
            )
            op.execute(f'DROP POLICY IF EXISTS "{MISS_READ_POLICY}" ON public."{table}"')
            op.execute(
                f'CREATE POLICY "{MISS_READ_POLICY}" ON public."{table}" '
                f"AS PERMISSIVE FOR SELECT TO {ALLY_APP_ROLE} "
                f"USING ({admin})"
            )
            continue

        if table in FOUNDER_TABLES:
            predicate = _predicate()
            op.execute(f'DROP POLICY IF EXISTS "{FOUNDER_POLICY}" ON public."{table}"')
            op.execute(
                f'CREATE POLICY "{FOUNDER_POLICY}" ON public."{table}" '
                f"AS PERMISSIVE FOR ALL TO {ALLY_APP_ROLE} "
                f"USING ({predicate}) WITH CHECK ({predicate})"
            )
        else:
            # `true` restricts no rows, and that is deliberate: these tables are
            # global. The protection here is that the policy names ally_app and
            # nothing else, so anon and authenticated match no policy and are
            # denied outright.
            op.execute(f'DROP POLICY IF EXISTS "{GLOBAL_POLICY}" ON public."{table}"')
            op.execute(
                f'CREATE POLICY "{GLOBAL_POLICY}" ON public."{table}" '
                f"AS PERMISSIVE FOR ALL TO {ALLY_APP_ROLE} "
                "USING (true) WITH CHECK (true)"
            )


def downgrade() -> None:
    """Puts the tables back the way they were, which is to say unprotected.

    Kept honest rather than made a no-op: a downgrade that silently leaves
    security in place is a downgrade that does not do what it says. Anyone
    running this is reopening the hole the upgrade closed.
    """
    for table in FOUNDER_TABLES + GLOBAL_TABLES + (MISS_TABLE,):
        if not _table_exists(table):
            continue
        for policy in (FOUNDER_POLICY, GLOBAL_POLICY, MISS_INSERT_POLICY, MISS_READ_POLICY):
            op.execute(f'DROP POLICY IF EXISTS "{policy}" ON public."{table}"')
        op.execute(f'ALTER TABLE public."{table}" DISABLE ROW LEVEL SECURITY')
