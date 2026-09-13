"""One-off: fill the 5 onboarding fields a seed defect left empty on real founders.

Found while trying to run scripts/e2e_journey_check.py against real Supabase
test accounts: `founders.profile_completed = true` on every candidate, but
`validate_profile()` -- the same check founder-dna/start enforces -- rejected
all of them, missing the identical five fields every time:

    Founder Reality, Invisible Gaps, Monthly Revenue, What It Is, Business Reality

Identical across every founder checked strongly suggests these accounts were
seeded directly (bypassing real onboarding) with profile_completed forced true
without the fields that flag is supposed to certify. This is a one-time,
by-hand fix for specific founder_ids -- not a general repair script, and it
touches nothing else on the row.

Values are plausible and stage-appropriate, not the founder's real answers --
there is no way to know those from here. Writing anything is a real decision
on a real account, so this refuses to run without --confirm-writes and prints
exactly what it is about to change before it changes it.

    python -m scripts.fill_missing_onboarding --database-url "..." --founder-id 7575 --confirm-writes
"""

from __future__ import annotations

import argparse
import os
import sys

FOUNDER_REALITY = {
    "clear_next_priorities": True,
    "decisive": True,
    "effort_aligned_to_growth": False,
    "executes_consistently": True,
    "mentally_clear": False,
}

BUSINESS_REALITY = {
    "revenue_predictable": False,
    "systems_defined": False,
    "plans_become_execution": True,
    "team_independent": False,
    "financials_clear": False,
}

INVISIBLE_GAPS = [
    "Working hard but results don't match",
    "Business depends heavily on me",
    "No clear roadmap",
]

FIELDS = {
    "founder_reality_signals": FOUNDER_REALITY,
    "business_reality_signals": BUSINESS_REALITY,
    "invisible_gaps": INVISIBLE_GAPS,
    "current_revenue": "under_1L",
    "product_description": (
        "A compliance-tracking tool for small Indian businesses, so they stop "
        "missing filing deadlines and paying late fees."
    ),
}


def run(args) -> int:
    os.environ["DATABASE_URL"] = args.database_url
    os.environ.setdefault("SECRET_KEY", "fill-missing-onboarding-not-a-real-secret")

    import sqlalchemy as sa

    from app.db.session import SessionLocal
    from app.models import Founder
    from app.services.profile_progress import validate_profile

    with SessionLocal() as db:
        founder = db.get(Founder, args.founder_id)
        if founder is None:
            print(f"No founder with founder_id={args.founder_id}")
            return 1

        before = validate_profile(founder)
        current = {
            col: getattr(founder, col, None)
            for col in FIELDS
        }
        print(f"founder_id={args.founder_id}  currently valid={before['valid']}")
        print("current values (only fields this script touches):")
        for col, val in current.items():
            print(f"  {col}: {val!r}")

        already_set = {c: v for c, v in current.items() if v not in (None, [], {}, "")}
        if already_set:
            print(f"\n  REFUSING: {list(already_set)} already has a value on "
                  "this founder. This script only fills genuinely empty "
                  "fields -- it will not overwrite anything.")
            return 1

        print("\nwill write:")
        for col, val in FIELDS.items():
            print(f"  {col} = {val!r}")

        if not args.confirm_writes:
            print("\nDry run. Re-run with --confirm-writes to apply.")
            return 0

        db.execute(
            sa.text("""
                update founders set
                  founder_reality_signals = cast(:fr as jsonb),
                  business_reality_signals = cast(:br as jsonb),
                  invisible_gaps = cast(:ig as jsonb),
                  current_revenue = :rev,
                  product_description = :pd
                where founder_id = :fid
            """),
            {
                "fr": _json(FIELDS["founder_reality_signals"]),
                "br": _json(FIELDS["business_reality_signals"]),
                "ig": _json(FIELDS["invisible_gaps"]),
                "rev": FIELDS["current_revenue"],
                "pd": FIELDS["product_description"],
                "fid": args.founder_id,
            },
        )
        db.commit()

        db.expire_all()
        founder = db.get(Founder, args.founder_id)
        after = validate_profile(founder)
        print(f"\nafter write: valid={after['valid']}")
        if not after["valid"]:
            print(f"  still missing: {[m['label'] for m in after['missing']]}")
    return 0


def _json(value) -> str:
    import json
    return json.dumps(value)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--database-url", required=True)
    p.add_argument("--founder-id", type=int, required=True)
    p.add_argument("--confirm-writes", action="store_true",
                   help="required to actually write; omit for a dry run")
    args = p.parse_args(argv)
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
