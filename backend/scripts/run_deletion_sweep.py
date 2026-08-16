"""Run the scheduled account-deletion sweep from outside the API process.

Why this exists
----------------
This backend runs as a persistent container with no in-process scheduler (see
DEPLOY.md), and `pg_cron` is not installed on the live Supabase project -- so
"scheduled" has to mean an external trigger. Two ways to drive it:

  1. HTTP: POST /api/v1/webhooks/deletion-sweep with the X-Webhook-Secret header
     (app/api/v1/webhooks/router.py) -- for a scheduler that can only make an HTTP
     call (a Supabase Database Webhook once pg_cron exists, GitHub Actions, an
     uptime-monitor-as-cron trick).
  2. This script: for a scheduler that can exec into the container/environment
     directly (a Render/Railway Cron Job, a Kubernetes CronJob, plain host cron).

Exit code is 0 even when some founders fail to erase (that is a normal, retryable
outcome the next sweep will pick back up -- see DeletionExecutor's docstring); it is
non-zero only if the sweep itself could not run at all.

Usage:
    python -m scripts.run_deletion_sweep [--batch-size 50]
"""

from __future__ import annotations

import argparse
import sys

from app.db.session import SessionLocal
from app.privacy.db_repository import SqlAlchemyDeletionRepository
from app.privacy.executor import DEFAULT_BATCH_SIZE, DeletionExecutor


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    args = parser.parse_args()

    db = SessionLocal()
    try:
        executor = DeletionExecutor(SqlAlchemyDeletionRepository(db))
        summary = executor.run_due(batch_size=args.batch_size)
    except Exception as exc:
        print(f"deletion sweep failed to run: {exc}", file=sys.stderr)
        return 1
    finally:
        db.close()

    print(f"checked={summary.checked} succeeded={summary.succeeded_count} "
          f"failed={summary.failed_count}")
    for outcome in summary.failed:
        print(f"  founder {outcome.founder_id} failed: {outcome.error}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
