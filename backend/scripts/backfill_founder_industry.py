"""One-off: link existing founders to an industry, and say who could not be.

WHAT THIS IS. The logic already exists as migration
`b7e4c85d2a19_backfill_founder_industry_link`. This is not new behaviour -- it
is the same UPDATE, runnable, because alembic cannot execute anything on these
databases: `alembic_version` carries an orphaned stamp (f8a3c26e4b91, in no file
in this repo) and the graph has ten heads, so `upgrade head` fails twice over.
Same situation and same remedy as scripts/_apply_dimension_code_column.py.

WHY IT MATTERS NOW. `founders.industry_mapped_id` is what every industry-aware
path reads -- the question gate, the relevance ranking, the opening block, the
reasoning service, the Ally context builder. A founder with NULL there gets the
universal bank and nothing else. That is correct behaviour (the feature fails
open, never guesses), but it means the whole industry feature is invisible for
every founder who has not saved their profile since FounderRepository.update()
started keeping the two columns in step.

WHAT IT DELIBERATELY WILL NOT DO. No fuzzy matching. Matching is exact on
`industry_name` or `industry_code`, case- and whitespace-insensitive, which is
the rule `FounderRepository.resolve_industry_id` applies at save time -- so a
founder linked here and one linked at save time can never disagree.

A founder whose stored industry does not match is left NULL rather than guessed
into the nearest-looking industry. Onboarding used to offer twelve one-word
industries ('AI', 'D2C', 'Healthcare', 'Agriculture', 'Real Estate') and those
are genuinely ambiguous against the thirty real ones -- 'AI' could be SaaS,
HealthTech or AdTech. Guessing would quietly feed a founder someone else's
diagnosis content, which is worse than the generic bank they get today.

So instead of guessing, it REPORTS every unmatched value with a count, and
prints the exact SQL to map one by hand if a human judges it unambiguous. That
judgement is theirs, not this script's.

Usage -- dry run is the default and writes nothing:

    python -m scripts.backfill_founder_industry
    python -m scripts.backfill_founder_industry --confirm-writes

Reads DATABASE_URL from the environment when --database-url is absent, so on
ECS it needs no arguments:

    aws ecs run-task --region ap-south-1 \
      --cluster ally-backend-cluster --task-definition ally_backend_task:<rev> \
      --launch-type FARGATE --count 1 \
      --network-configuration "awsvpcConfiguration={subnets=[...],securityGroups=[...],assignPublicIp=ENABLED}" \
      --overrides '{"containerOverrides":[{"name":"Main","command":[
         "python","-m","scripts.backfill_founder_industry","--confirm-writes"]}]}'
"""

from __future__ import annotations

import argparse
import os
import sys

import sqlalchemy as sa

#: The migration's UPDATE, verbatim. Kept identical on purpose: if this and the
#: migration ever disagree, a founder's industry would depend on which one
#: happened to run, which is exactly the drift resolve_industry_id exists to
#: prevent.
_BACKFILL = """
UPDATE founders AS f
   SET industry_mapped_id = i.industry_id
  FROM industries AS i
 WHERE f.industry_mapped_id IS NULL
   AND f.industry IS NOT NULL
   AND btrim(f.industry) <> ''
   AND (
         lower(btrim(f.industry)) = lower(i.industry_name)
      OR lower(btrim(f.industry)) = lower(i.industry_code)
       )
"""

_DISTRIBUTION = """
SELECT COALESCE(NULLIF(btrim(f.industry), ''), '(never answered)') AS stored,
       count(*)                                                    AS founders,
       count(f.industry_mapped_id)                                 AS linked,
       EXISTS (SELECT 1 FROM industries i
                WHERE lower(btrim(f.industry)) IN (lower(i.industry_name),
                                                   lower(i.industry_code)))
                                                                   AS matchable
  FROM founders f
 GROUP BY 1, 4
 ORDER BY founders DESC, stored
"""

_TOTALS = """
SELECT count(*)                                         AS founders,
       count(industry_mapped_id)                        AS linked,
       count(*) FILTER (WHERE industry IS NULL
                           OR btrim(industry) = '')     AS never_answered
  FROM founders
"""


def _report(conn) -> tuple[int, int, int, list]:
    total, linked, blank = conn.execute(sa.text(_TOTALS)).one()
    rows = conn.execute(sa.text(_DISTRIBUTION)).all()

    print("=" * 72)
    print(f"{'stored industry':<34}{'founders':>9}{'linked':>8}{'':>4}")
    print("=" * 72)
    for stored, founders, already, matchable in rows:
        note = "" if stored == "(never answered)" else (
            "  matches" if matchable else "  NO MATCH")
        print(f"{stored[:33]:<34}{founders:>9}{already:>8}{note}")
    print("-" * 72)
    print(f"{'TOTAL':<34}{total:>9}{linked:>8}")
    print(f"\n  never answered the industry question : {blank}")
    return total, linked, blank, rows


def run(args) -> int:
    url = args.database_url or os.environ.get("DATABASE_URL")
    if not url:
        print("No --database-url and no DATABASE_URL in the environment.")
        return 2

    engine = sa.create_engine(url, poolclass=sa.pool.NullPool)

    with engine.connect() as conn:
        print("\nBEFORE\n")
        _total, linked_before, blank, rows = _report(conn)

    will_link = sum(f - a for _s, f, a, m in rows if m)
    unmatched = [(s, f) for s, f, _a, m in rows
                 if not m and s != "(never answered)"]

    print(f"\n  this run would link : {will_link} founder(s)")
    if unmatched:
        print(f"  cannot be matched   : {sum(f for _s, f in unmatched)} founder(s)")
        print("\n  These stored values match no industry_name and no industry_code.")
        print("  They are NOT guessed -- see the module docstring. If a human")
        print("  judges one unambiguous, map it explicitly:\n")
        for stored, founders in unmatched:
            print(f"    -- {founders} founder(s) stored {stored!r}")
            print(f"    UPDATE founders SET industry = '<exact industries.industry_name>'")
            print(f"     WHERE industry_mapped_id IS NULL AND btrim(industry) = '{stored}';")
        print("\n  then re-run this script.")

    if blank:
        print(f"\n  {blank} founder(s) never answered the industry question, so")
        print("  nothing can link them. They will keep getting the universal")
        print("  bank until they complete or re-save onboarding -- which is the")
        print("  correct behaviour, not a failure.")

    if not args.confirm_writes:
        print("\n  Dry run. Nothing was written.")
        print("  Re-run with --confirm-writes to apply.")
        return 0

    if will_link == 0:
        print("\n  Nothing to link. No write attempted.")
        return 0

    with engine.begin() as conn:
        updated = conn.execute(sa.text(_BACKFILL)).rowcount

    with engine.connect() as conn:
        print(f"\n  linked: {updated}\n\nAFTER\n")
        _total, linked_after, _blank, _rows = _report(conn)

    if linked_after != linked_before + updated:
        print(f"\n  VERIFICATION FAILED: linked went {linked_before} -> "
              f"{linked_after}, expected {linked_before + updated}")
        return 1

    print(f"\n  VERIFIED. {linked_after} founder(s) now carry an industry.")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--database-url", default=None,
                   help="defaults to $DATABASE_URL, which ECS already sets")
    p.add_argument("--confirm-writes", action="store_true",
                   help="without this nothing is written")
    return run(p.parse_args(argv))


if __name__ == "__main__":
    sys.exit(main())
