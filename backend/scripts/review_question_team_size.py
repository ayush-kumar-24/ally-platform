"""Finish the `questions.min_team_size` review that migration d4a1f8c62b73 starts.

The migration sets every Team & Leadership question to '2_5' -- the reviewed
default for a pillar whose three dimensions all presuppose people other than
the founder -- and opens the 45 Stage 0 questions it read individually back to
'solo'. Stage 0→1 and Stage 1→10+ are still at the default, which means a
founder working alone is asked none of them. Some of them they could answer.

Telling which needs a person to read the question. That is what this is for,
and like `backfill_problem_dimensions.py` it does not guess:

    --report   Print the questions still at the default, grouped by
               (stage group, dimension, subcategory) and, inside a group,
               ordered so questions that share a shape sit together. That
               grouping IS the worksheet: questions in one group usually take
               the same answer.

    --apply FILE
               Apply a reviewed assignment file. JSON, keyed by question code:

                   {"S0-AGR-205-2": "solo",
                    "TM-003":       "2_5",
                    "PM-014":       "6_10"}

               Every value must be one of founders.team_size's six bands, so a
               question can never require a size a founder has no way to state.

Nothing is written without --apply, and --apply is a dry run unless --commit.

WHAT TO ASK YOURSELF about each question, since the migration's own notes are
the precedent to stay consistent with:

  * Can someone with nobody else in the business answer this AS ASKED? Not
    "could they say something" -- "Who handles a customer dispute?" can be
    answered "me", but it is put as though work is divided and the report reads
    the answer that way. That stays at '2_5'.
  * A question about a rule being written down, a cost the founder knows, or
    what they intend to do later is answerable alone. A question about what
    somebody else did, decided or was like is not.
  * Past tense about a person already taken on ("when you last hired...") is
    never 'solo'.

Usage:
    DATABASE_URL=... SECRET_KEY=... python -m scripts.review_question_team_size --report
    DATABASE_URL=... SECRET_KEY=... python -m scripts.review_question_team_size \
        --apply team_size.json [--commit]
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict

from sqlalchemy import text

from app.db.session import SessionLocal

#: founders.team_size's five bands. A question may not require anything else.
#: "26_50" and "50_plus" were merged into "26_plus" by d71a4e8c3f05 and are
#: deliberately absent: this tool writes, and nothing may newly write a retired
#: band.
BANDS = ("solo", "2_5", "6_10", "11_25", "26_plus")

#: The value migration d4a1f8c62b73 leaves behind as "not yet read".
DEFAULT_BAND = "2_5"

_TEAM_PILLAR_ID = 5


def _load(db):
    rows = db.execute(
        text(
            """
            SELECT q.question_code, q.question_text, q.min_team_size,
                   q.primary_stage_group, p.subcategory, p.problem_name,
                   p.dimension_code, p.pillar_id
            FROM questions q
            JOIN problems p ON p.problem_id = q.problem_id
            WHERE p.pillar_id = :pillar
            ORDER BY q.primary_stage_group, p.dimension_code NULLS FIRST,
                     p.subcategory NULLS FIRST, q.question_code
            """
        ),
        {"pillar": _TEAM_PILLAR_ID},
    ).mappings().all()
    return [dict(r) for r in rows]


def report(questions) -> int:
    reviewed = [q for q in questions if q["min_team_size"] != DEFAULT_BAND]
    pending = [q for q in questions if q["min_team_size"] == DEFAULT_BAND]

    print(f"Team & Leadership questions: {len(questions)} total, "
          f"{len(reviewed)} moved off the default, {len(pending)} still at "
          f"'{DEFAULT_BAND}'")

    by_band: dict[str, int] = defaultdict(int)
    for q in questions:
        by_band[q["min_team_size"] or "NULL"] += 1
    for band, n in sorted(by_band.items(), key=lambda x: -x[1]):
        print(f"  {n:5d}  {band}")

    solo_by_stage: dict[str, int] = defaultdict(int)
    for q in questions:
        if q["min_team_size"] == "solo":
            solo_by_stage[q["primary_stage_group"] or "(untagged)"] += 1
    print("\nWhat a founder working alone is asked today, by stage group:")
    stages = sorted({q["primary_stage_group"] or "(untagged)" for q in questions})
    for stage in stages:
        print(f"  {solo_by_stage.get(stage, 0):5d}  {stage}")

    if not pending:
        print("\nNothing left to review.")
        return 0

    print("\n--- still at the default, grouped as the review should work through them ---")
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for q in pending:
        groups[(q["primary_stage_group"], q["dimension_code"], q["subcategory"])].append(q)

    for (stage, dimension, subcategory), items in sorted(
        groups.items(), key=lambda g: (str(g[0][0]), -len(g[1]))
    ):
        print(f"\n  {stage} / {dimension or '(no dimension)'} / "
              f"{subcategory or '(no subcategory)'}  -- {len(items)} question(s)")
        for q in items[:12]:
            print(f"      {q['question_code']:<16} {q['question_text'][:88]}")
        if len(items) > 12:
            print(f"      ... and {len(items) - 12} more")

    print("\nWrite the decisions to a JSON file keyed by question code and "
          "re-run with --apply.")
    return 0


def apply(db, questions, path: str, commit: bool) -> int:
    spec = json.loads(open(path, encoding="utf-8").read())
    by_code = {q["question_code"]: q for q in questions}
    errors: list[str] = []

    # Validate the whole file before writing any of it: a half-applied file is
    # worse than a rejected one, because the half that landed looks reviewed.
    for code, band in spec.items():
        if code not in by_code:
            errors.append(f"{code}: no such Team & Leadership question")
        elif band not in BANDS:
            errors.append(f"{code}: {band!r} is not one of {', '.join(BANDS)}")

    if errors:
        print(f"REFUSED, {len(errors)} problem(s) with the assignment file:")
        for e in errors:
            print(f"  {e}")
        return 1

    changed = [
        (code, band) for code, band in spec.items()
        if by_code[code]["min_team_size"] != band
    ]
    print(f"{len(spec)} assignment(s) in file, {len(changed)} would change a row.")
    for code, band in changed[:40]:
        was = by_code[code]["min_team_size"] or "NULL"
        print(f"  {code:<16} {was} -> {band}  {by_code[code]['question_text'][:54]}")
    if len(changed) > 40:
        print(f"  ... and {len(changed) - 40} more")

    if not commit:
        print("\nDry run. Re-run with --commit to write.")
        return 0

    for code, band in changed:
        db.execute(
            text("UPDATE questions SET min_team_size = :b WHERE question_code = :c"),
            {"b": band, "c": code},
        )
    db.commit()
    print(f"\nWrote {len(changed)} row(s).")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--report", action="store_true",
                       help="print the questions still at the default, grouped for review")
    group.add_argument("--apply", metavar="FILE",
                       help="apply a reviewed JSON assignment file")
    parser.add_argument("--commit", action="store_true",
                        help="with --apply, actually write (default is a dry run)")
    args = parser.parse_args(argv)

    db = SessionLocal()
    try:
        questions = _load(db)
        if not questions:
            print("No Team & Leadership questions found -- is this the right database?")
            return 1
        if args.report:
            return report(questions)
        return apply(db, questions, args.apply, args.commit)
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
