"""Clear every founder's diagnosis history so they can run a diagnosis again.

Written to be run INSIDE the running container (ECS exec), because the
production RDS instance is not publicly reachable -- it resolves to a private
VPC address and 5432 is closed from outside. The container already holds
DATABASE_URL from Secrets Manager, so nobody has to handle the credentials:
this reads it from the environment and never prints it.

The image is python:3.11-slim with no psql client, which is why this is Python
rather than the .sql pair in the repo root.

    # look, change nothing:
    python scripts/reset_diagnosis_data.py

    # actually delete:
    python scripts/reset_diagnosis_data.py --apply

KEEPS founders (the accounts themselves) and every reference/catalogue table --
questions, problems, root_causes, interventions, frameworks. Only a founder's
own diagnosis history goes.

Take an RDS snapshot first. There is no undo:

    aws rds create-db-snapshot --region ap-south-1 \
        --db-instance-identifier ally-postgres \
        --db-snapshot-identifier ally-prod-before-diagnosis-reset
"""

from __future__ import annotations

import argparse
import os
import sys
from urllib.parse import urlparse

import psycopg

# Children before parents. founder_feedback -> founder_reports/sessions and
# stage_assessments -> sessions are both ON DELETE SET NULL, so they are cleared
# explicitly rather than being quietly detached and left behind.
DELETE_ORDER = (
    "founder_feedback",
    "internal_intelligence_reports",
    "founder_reports",
    "detected_root_causes",
    "stage_assessments",
    "answers",
    "founder_dna_answers",
    "current_problem_answers",
    # Deleting sessions is what actually unblocks a retest: the lifetime limit
    # is count_completed_sessions(), not a boolean on founders.
    "sessions",
    # Derived state. Without these a "fresh" diagnosis still starts primed with
    # everything Ally previously concluded about the founder.
    "founder_memory_events",
    "founder_memory",
    "founder_context",
    # Chat. suggestions CASCADEs from conversations, and messages is partitioned
    # and CASCADEs too -- both go with this one delete.
    "conversations",
)

# Counted before and after, including the ones that disappear via CASCADE so the
# cascade is visible rather than implied.
COUNT_TABLES = DELETE_ORDER + ("messages", "suggestions")

# Cleared so founders are asked the Founder DNA and current-problem questions
# again instead of skipping straight past them. --keep-phase-flags leaves them.
PHASE_FLAG_SQL = """
UPDATE founders SET
    founder_dna_completed_at        = NULL,
    founder_dna_resolved_dimensions = '[]'::jsonb,
    current_problem_completed_at    = NULL,
    diagnosis_used                  = false,
    diagnosis_locked_at             = NULL
"""


def _counts(cur, tables) -> dict[str, int]:
    out = {}
    for table in tables:
        try:
            cur.execute(f"SELECT count(*) FROM {table}")
            out[table] = cur.fetchone()[0]
        except psycopg.Error:
            out[table] = -1  # table absent in this environment
            cur.connection.rollback()
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true",
                    help="actually delete. Without it this only reports.")
    ap.add_argument("--keep-phase-flags", action="store_true",
                    help="leave founder_dna_completed_at etc. set, so founders "
                         "keep their DNA and only redo the business diagnosis.")
    args = ap.parse_args()

    url = os.environ.get("DATABASE_URL")
    if not url:
        print("DATABASE_URL is not set in this environment.", file=sys.stderr)
        return 2

    # Prove which database this is before touching it. The whole reason this
    # script exists is that a wipe was once applied to the Supabase copy while
    # production reads RDS, and both hold the same schema so nothing looked wrong.
    # SQLAlchemy's driver-qualified scheme is not valid libpq conninfo -- psycopg
    # rejects "postgresql+psycopg://" outright, and its error echoes the whole
    # string, password included. Normalise once and use it for both the host
    # check and the connection.
    dsn = url.replace("postgresql+psycopg://", "postgresql://", 1)
    host = urlparse(dsn).hostname or "?"
    print(f"host     : {host}")
    if "rds.amazonaws.com" not in host:
        print("  !! this is NOT an RDS host. If you meant production, stop here.")

    with psycopg.connect(dsn, autocommit=False) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT current_database(), current_user, version()")
            db, user, version = cur.fetchone()
            print(f"database : {db}\nuser     : {user}\nserver   : {version.split(',')[0]}\n")

            before = _counts(cur, COUNT_TABLES)
            cur.execute("SELECT count(*) FROM founders")
            founders_before = cur.fetchone()[0]
            cur.execute("SELECT count(DISTINCT founder_id) FROM sessions")
            affected = cur.fetchone()[0]

            print(f"{'table':32} {'rows':>8}")
            for table, n in before.items():
                print(f"{table:32} {n if n >= 0 else 'absent':>8}")
            print(f"\nfounders (kept)                  {founders_before:>8}")
            print(f"founders with a session          {affected:>8}")

            if not args.apply:
                print("\nDRY RUN -- nothing deleted. Re-run with --apply to delete.")
                return 0

            print("\napplying...")
            for table in DELETE_ORDER:
                if before.get(table, -1) < 0:
                    continue
                cur.execute(f"DELETE FROM {table}")
                print(f"  deleted {cur.rowcount:>6} from {table}")

            if not args.keep_phase_flags:
                cur.execute(PHASE_FLAG_SQL)
                print(f"  reset phase flags on {cur.rowcount} founders")

            after = _counts(cur, COUNT_TABLES)
            cur.execute("SELECT count(*) FROM founders")
            founders_after = cur.fetchone()[0]

            leftover = {t: n for t, n in after.items() if n > 0}
            if leftover or founders_after != founders_before:
                conn.rollback()
                print("\nROLLED BACK -- unexpected state after delete:")
                for t, n in leftover.items():
                    print(f"  {t} still has {n} rows")
                if founders_after != founders_before:
                    print(f"  founders changed {founders_before} -> {founders_after}")
                return 1

            conn.commit()
            print(f"\nCOMMITTED. founders kept: {founders_after}")
            print("Every founder can now run a diagnosis again.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
