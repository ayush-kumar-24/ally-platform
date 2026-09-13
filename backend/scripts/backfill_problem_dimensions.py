"""Finish the `problems.dimension_code` backfill that migration c3f7b28d5e91 starts.

The migration fills only the five categories that map 1:1 onto a Business DNA
Part 2 dimension. The rest cannot be assigned from anything this repository
holds -- 204 of the 273 problems appear in no snapshot here, and the categories
that do appear mostly span three of their pillar's dimensions at once. Telling
them apart needs `problems.problem_name` and `problems.subcategory`, which only
exist in the live database.

So this is two tools in one, and neither of them guesses:

    --report   Print every unmapped problem, grouped by (pillar, category,
               subcategory), with its name and how many questions hang off it.
               That grouping IS the content pass's worksheet: problems in one
               group almost always take the same dimension.

    --apply FILE
               Apply a reviewed assignment file. JSON, either shape:

                   {"by_problem_id":  {"137": "prioritization_discipline"},
                    "by_subcategory": {"Sales Technology": null}}

               `null` records "no dimension in Part 2's twenty" explicitly, so a
               later run stops re-reporting it as unreviewed. by_problem_id wins
               over by_subcategory.

Nothing is written without --apply, and --apply refuses any assignment whose
dimension sits in a different pillar than the problem does: the Business Health
Score attributes answers by pillar_id, so a cross-pillar dimension would score
under one pillar and report under another.

Usage:
    DATABASE_URL=... SECRET_KEY=... python -m scripts.backfill_problem_dimensions --report
    DATABASE_URL=... SECRET_KEY=... python -m scripts.backfill_problem_dimensions \
        --apply dimensions.json [--commit]
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict

from sqlalchemy import text

from app.api.v1.diagnosis.business_dna import (
    CATEGORIES_WITHOUT_A_DIMENSION,
    DIMENSION_BY_CODE,
    PILLAR_NAMES,
)
from app.db.session import SessionLocal


def _load_problems(db):
    rows = db.execute(
        text(
            """
            SELECT p.problem_id, p.problem_name, p.category, p.subcategory,
                   p.pillar_id, p.dimension_code,
                   (SELECT count(*) FROM questions q
                     WHERE q.problem_id = p.problem_id) AS question_count
            FROM problems p
            ORDER BY p.pillar_id, p.category, p.subcategory NULLS FIRST, p.problem_id
            """
        )
    ).mappings().all()
    return [dict(r) for r in rows]


def report(problems) -> int:
    mapped = [p for p in problems if p["dimension_code"]]
    unmapped = [p for p in problems if not p["dimension_code"]]
    q_total = sum(p["question_count"] for p in problems)
    q_mapped = sum(p["question_count"] for p in mapped)

    print(f"problems: {len(mapped)} mapped, {len(unmapped)} unmapped, {len(problems)} total")
    print(f"questions reachable by dimension: {q_mapped} of {q_total}")

    if mapped:
        print("\n--- already mapped ---")
        by_dim: dict[str, int] = defaultdict(int)
        for p in mapped:
            by_dim[p["dimension_code"]] += p["question_count"]
        for code, n in sorted(by_dim.items(), key=lambda x: -x[1]):
            dim = DIMENSION_BY_CODE.get(code)
            name = dim.name if dim else f"{code} (NOT A PART 2 DIMENSION)"
            print(f"  {n:5d} questions  {name}")

    if not unmapped:
        print("\nNothing left to assign.")
        return 0

    print("\n--- unmapped, grouped as the content pass should work through them ---")
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for p in unmapped:
        groups[(p["pillar_id"], p["category"], p["subcategory"])].append(p)

    for (pillar_id, category, subcategory), items in sorted(
        groups.items(), key=lambda g: -sum(p["question_count"] for p in g[1])
    ):
        pillar = PILLAR_NAMES.get(pillar_id, f"pillar {pillar_id}")
        note = CATEGORIES_WITHOUT_A_DIMENSION.get(category, "")
        candidates = [d.code for d in DIMENSION_BY_CODE.values() if d.pillar_id == pillar_id]
        qn = sum(p["question_count"] for p in items)
        print(f"\n  {pillar} / {category} / {subcategory or '(no subcategory)'}")
        print(f"    {len(items)} problem(s), {qn} question(s)"
              + (f"  [{note}]" if note else ""))
        print(f"    candidates in this pillar: {', '.join(candidates) or '(none)'}")
        for p in items[:8]:
            print(f"      {p['problem_id']:>4}  {p['problem_name'][:76]}")
        if len(items) > 8:
            print(f"      ... and {len(items) - 8} more")

    print(
        "\nWrite the decisions to a JSON file and re-run with --apply. Use null for "
        "\"no dimension in Part 2's twenty\" so it stops being reported as unreviewed."
    )
    return 0


def apply(db, problems, path: str, commit: bool) -> int:
    spec = json.loads(open(path, encoding="utf-8").read())
    by_problem = {int(k): v for k, v in (spec.get("by_problem_id") or {}).items()}
    by_subcat = spec.get("by_subcategory") or {}

    by_id = {p["problem_id"]: p for p in problems}
    planned: list[tuple[int, str | None]] = []
    errors: list[str] = []

    for problem_id, code in by_problem.items():
        if problem_id not in by_id:
            errors.append(f"problem_id {problem_id} does not exist")
            continue
        planned.append((problem_id, code))

    for subcategory, code in by_subcat.items():
        for p in problems:
            if p["subcategory"] == subcategory and p["problem_id"] not in by_problem:
                planned.append((p["problem_id"], code))

    # Validate before writing anything: a half-applied assignment file is worse
    # than a rejected one, because the half that landed looks reviewed.
    for problem_id, code in planned:
        if code is None:
            continue
        dim = DIMENSION_BY_CODE.get(code)
        if dim is None:
            errors.append(f"problem {problem_id}: {code!r} is not a Part 2 dimension")
            continue
        pillar_id = by_id[problem_id]["pillar_id"]
        if dim.pillar_id != pillar_id:
            errors.append(
                f"problem {problem_id} is pillar {pillar_id} but {code!r} is "
                f"pillar {dim.pillar_id} -- it would score under one pillar and "
                "report under another"
            )

    if errors:
        print(f"REFUSED, {len(errors)} problem(s) with the assignment file:")
        for e in errors:
            print(f"  {e}")
        return 1

    changed = [
        (pid, code) for pid, code in planned if by_id[pid]["dimension_code"] != code
    ]
    print(f"{len(planned)} assignment(s) in file, {len(changed)} would change a row.")
    for pid, code in changed[:40]:
        was = by_id[pid]["dimension_code"]
        print(f"  {pid:>4}  {was or 'NULL'} -> {code or 'NULL'}  {by_id[pid]['problem_name'][:56]}")
    if len(changed) > 40:
        print(f"  ... and {len(changed) - 40} more")

    if not commit:
        print("\nDry run. Re-run with --commit to write.")
        return 0

    for pid, code in changed:
        db.execute(
            text("UPDATE problems SET dimension_code = :d WHERE problem_id = :p"),
            {"d": code, "p": pid},
        )
    db.commit()
    print(f"\nWrote {len(changed)} row(s).")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--report", action="store_true",
                       help="print unmapped problems, grouped for review")
    group.add_argument("--apply", metavar="FILE",
                       help="apply a reviewed JSON assignment file")
    parser.add_argument("--commit", action="store_true",
                        help="with --apply, actually write (default is a dry run)")
    args = parser.parse_args(argv)

    db = SessionLocal()
    try:
        problems = _load_problems(db)
        if args.report:
            return report(problems)
        return apply(db, problems, args.apply, args.commit)
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
