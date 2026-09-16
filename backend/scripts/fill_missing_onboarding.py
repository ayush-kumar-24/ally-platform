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
there is no way to know those from here. current_revenue follows the founder's
stage: "pre_revenue" at Ideation, "1L_5L" at Early Traction, "25L_1Cr" at
Growth, because a Growth-stage founder billing under a lakh is a contradiction
the diagnosis would then be asked to account for.

ONLY EMPTY FIELDS ARE WRITTEN. A column that already holds something is listed
and skipped; nothing a founder actually answered is ever overwritten. It used
to refuse outright if ANY of the five had a value, which made it useless for
exactly the accounts it was written for -- every seeded founder past Ideation
has invisible_gaps set and the other four empty, so it declined all of them.

Writing anything is a real decision on a real account, so this refuses to run
without --confirm-writes and prints exactly what it is about to change first.

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

# current_revenue by stage, because "under_1L" on a Growth/Scaling founder is
# not a plausible value -- it is a contradiction the diagnosis would then be
# asked to explain. Bands are the ones founders_current_revenue_check allows.
# Anything not listed keeps the default above.
REVENUE_BY_STAGE_ORDER = {
    1: "pre_revenue",     # Ideation
    2: "pre_revenue",     # Validation
    3: "under_1L",        # Prototype / MVP
    4: "1L_5L",           # Early Traction
    5: "25L_1Cr",         # Growth / Scaling
    6: "above_1Cr",       # Expansion
    7: "above_1Cr",       # Maturity
    8: "above_1Cr",       # Exit
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

        # FILL THE EMPTY ONES, LEAVE THE REST. This used to refuse outright
        # when ANY of the five already had a value, which made it unusable for
        # the founders that need it most: every seeded account past Ideation
        # has invisible_gaps set and the other four empty, so the script that
        # exists to unblock them declined all of them. The guarantee that
        # matters -- never overwrite a value a founder gave -- is kept by
        # filtering, not by refusing.
        already_set = {c: v for c, v in current.items() if v not in (None, [], {}, "")}
        to_write = {c: v for c, v in FIELDS.items() if c not in already_set}

        if already_set:
            print(f"\n  leaving alone (already has a value): {list(already_set)}")
        if not to_write:
            print("\n  nothing to do: every field this script fills is already "
                  "set. If the profile is still rejected, the missing field is "
                  "one this script does not touch -- run the journey check to "
                  "see which.")
            return 1

        # Stage decides the revenue band, when that is one of the empty ones.
        stage_order = db.execute(sa.text(
            "select stage_order from founder_stages where stage_id = :s"),
            {"s": founder.stage_id}).scalar()
        if "current_revenue" in to_write and stage_order in REVENUE_BY_STAGE_ORDER:
            to_write["current_revenue"] = REVENUE_BY_STAGE_ORDER[stage_order]
            print(f"\n  stage_order {stage_order} -> current_revenue "
                  f"{to_write['current_revenue']!r}")

        print("\nwill write:")
        for col, val in to_write.items():
            print(f"  {col} = {val!r}")

        if not args.confirm_writes:
            print("\nDry run. Re-run with --confirm-writes to apply.")
            return 0

        # Built from `to_write`, so a column that was already populated never
        # appears in the statement at all.
        jsonb_columns = {"founder_reality_signals", "business_reality_signals",
                         "invisible_gaps"}
        assignments, params = [], {"fid": args.founder_id}
        for i, (col, val) in enumerate(to_write.items()):
            key = f"v{i}"
            cast = f"cast(:{key} as jsonb)" if col in jsonb_columns else f":{key}"
            assignments.append(f"{col} = {cast}")
            params[key] = _json(val) if col in jsonb_columns else val

        db.execute(
            sa.text(f"update founders set {', '.join(assignments)} "
                    "where founder_id = :fid"),
            params,
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
