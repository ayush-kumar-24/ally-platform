"""What would this founder actually be asked? A read-only end-to-end check.

WHY THIS EXISTS. The industry work (question_industry_mapping gate, relevance
ranking, opening block) is covered by 110 unit tests, and every one of them uses
fabricated data. None of them can tell you whether the DATABASE a deployment
actually talks to carries the rows the feature reads. That distinction is not
academic: the feature is deliberately fail-open, so a database missing
`question_industry_mapping` disables the whole of it silently -- no error, no log
line at startup, no wrong answer. It simply behaves as it did before any of it
was written, and the 1,800 industry questions go back to being eligible for
every founder.

So this runs the REAL engine -- the same `candidate_questions` and
`order_candidates` a live request calls -- against whatever DATABASE_URL it is
given, and prints the question sequence a founder would actually receive.

It writes NOTHING. No session is created, no answer is stored, no row is
touched. The founder and session are in-memory stand-ins; the repository only
ever uses their ids as query parameters, so an id that matches nothing simply
means "no answers yet", which is exactly the state being simulated.

Run it locally against a dev database, or against production the same way
DEPLOY.md runs any other one-off (RDS is not reachable from outside the VPC):

    aws ecs run-task --region ap-south-1 \
      --cluster ally-backend-cluster --task-definition ally_backend_task:<rev> \
      --launch-type FARGATE --count 1 \
      --network-configuration "awsvpcConfiguration={subnets=[...],securityGroups=[...],assignPublicIp=ENABLED}" \
      --overrides '{"containerOverrides":[{"name":"Main","command":[
         "python","-m","scripts.qa.industry_selection_preflight","--preflight"]}]}'

    DATABASE_URL=... SECRET_KEY=... python -m scripts.qa.industry_selection_preflight \
        --industry saas --stage 6
    ... --compare saas,logistics --stage 6
    ... --preflight
"""

from __future__ import annotations

import argparse
import sys
from types import SimpleNamespace

from sqlalchemy import text

from app.api.v1.diagnosis.engine import QuestionSelectionEngine, resolve_stage_groups
from app.api.v1.diagnosis.repository import DiagnosisRepository
from app.api.v1.diagnosis.stage_scope import resolve_scope
from app.core.config import settings
from app.db.session import SessionLocal

PILLARS = {1: "Founder Readiness", 2: "Market Clarity", 3: "Revenue Maturity",
           4: "Product & Execution", 5: "Team & Leadership", 6: "Strategic Clarity"}


# --- preflight: does this database carry what the feature reads? -----------

def preflight(db) -> int:
    """Answer the one question the unit tests cannot: is the feature ON here?

    Returns a process exit code, so this doubles as a deploy gate.
    """
    print("=" * 72)
    print("PREFLIGHT -- can the industry feature work against this database?")
    print("=" * 72)

    problems: list[str] = []

    def check(label, sql, ok, detail=""):
        try:
            value = db.execute(text(sql)).scalar()
        except Exception as exc:                           # noqa: BLE001
            print(f"  [MISSING] {label}\n             {type(exc).__name__}: "
                  f"{str(exc).splitlines()[0][:90]}")
            problems.append(label)
            return None
        good = ok(value)
        print(f"  [{'OK' if good else 'EMPTY'}]   {label}: {value}{detail}")
        if not good:
            problems.append(label)
        return value

    check("alembic_version", "select version_num from alembic_version", lambda v: bool(v))
    mapping = check("question_industry_mapping rows",
                    "select count(*) from question_industry_mapping", lambda v: v and v > 0,
                    "   <- the gate, the ranking and the opening block ALL read this")
    check("industries rows", "select count(*) from industries", lambda v: v and v > 0)
    check("industries with pain-point weights",
          "select count(*) from industries where top_pain_point_weights <> '{}'::jsonb",
          lambda v: v is not None,
          "   <- 0 only weakens ranking, never breaks it")
    check("founders with an industry linked",
          "select count(*) from founders where industry_mapped_id is not null",
          lambda v: v is not None,
          "   <- 0 means the feature is off for every founder")
    check("industry-owned questions in the bank",
          "select count(*) from questions where industry_relevance is not null "
          "and industry_relevance <> '[\"all\"]'::jsonb", lambda v: v is not None)

    print()
    if mapping in (None, 0):
        print("  VERDICT: the industry feature is OFF on this database.")
        print("           It fails open by design, so nothing errors -- but the")
        print("           1,800 industry questions are eligible for EVERY founder,")
        print("           which is the original bug. Run `alembic upgrade head`.")
    elif problems:
        print(f"  VERDICT: partially ready. Weak: {', '.join(problems)}")
    else:
        print("  VERDICT: the industry feature is live on this database.")
    print()
    return 1 if mapping in (None, 0) else 0


# --- the simulation --------------------------------------------------------

def _founder(db, industry_code: str | None, stage_order: int):
    """An in-memory founder. Nothing is inserted."""
    industry_id = None
    industry_name = None
    if industry_code:
        row = db.execute(
            text("select industry_id, industry_name from industries "
                 "where lower(industry_code) = lower(:c)"),
            {"c": industry_code},
        ).first()
        if row is None:
            sys.exit(f"No industry with code {industry_code!r}. "
                     "Run with --list-industries to see the options.")
        industry_id, industry_name = row

    stage = db.execute(
        text("select stage_id, stage_name, stage_order, question_budget "
             "from founder_stages where stage_order = :o"),
        {"o": stage_order},
    ).first()
    if stage is None:
        sys.exit(f"No founder stage with stage_order {stage_order}.")

    founder = SimpleNamespace(
        founder_id=-1,                       # matches no real founder
        industry_mapped_id=industry_id,
        industry=industry_name,
        current_challenges=None,             # unknown -> fundraising gate fails open
        stage=SimpleNamespace(stage_id=stage[0], stage_name=stage[1],
                              stage_order=stage[2], question_budget=stage[3]),
    )
    return founder, industry_name, stage


def simulate(db, industry_code: str | None, stage_order: int, show: int):
    repo = DiagnosisRepository(db)
    engine = QuestionSelectionEngine(repo)
    founder, industry_name, stage = _founder(db, industry_code, stage_order)
    session = SimpleNamespace(
        session_id=-1, routing_state="continue",
        founder_industry_id=founder.industry_mapped_id,
        questions_answered_count=0,          # start of the diagnosis
    )

    budget = settings.question_budget(stage[3])
    scope = resolve_scope(founder)
    block = engine._opening_block_size(session, founder)

    print("=" * 72)
    print(f"FOUNDER  stage {stage[2]} ({stage[1]})   industry: {industry_name or 'none'}")
    print("=" * 72)
    print(f"  stage groups eligible : {', '.join(resolve_stage_groups(founder))}")
    print(f"  pillars in scope      : "
          f"{', '.join(PILLARS[p] for p in sorted(scope.pillars)) if scope else 'all'}")
    print(f"  question budget       : {budget}")
    print(f"  industry opening block: {block}"
          f"{'   <- ZERO: the feature is not active here' if block == 0 else ''}")

    candidates = engine.candidate_questions(session, founder)
    print(f"  eligible questions    : {len(candidates)}")
    if not candidates:
        print("\n  Nothing eligible -- that is a data problem, not a selection one.")
        return

    ordered = engine.order_candidates(candidates, session, founder)
    owned = repo.question_owned_by_industry() if _safe(repo) else {}
    code = (industry_code or "").casefold()
    pillar_of = repo.problem_to_pillar()

    print(f"\n  The first {min(show, budget)} questions, in order:\n")
    seen_pillars: set[int] = set()
    for n, q in enumerate(ordered[:min(show, budget)], 1):
        industries = owned.get(q.question_id, frozenset())
        tag = ("[OWN INDUSTRY]" if any(c.casefold() == code for c in industries)
               else f"[{'/'.join(sorted(industries))}]" if industries else "[universal]")
        pillar = pillar_of.get(q.problem_id)
        seen_pillars.add(pillar) if pillar else None
        marker = "|" if n <= block else " "
        print(f"  {marker}{n:>3}. {tag:<16} P{pillar or '?'} {q.category[:22]:<22} "
              f"{q.question_text[:60]}")
    if block:
        print(f"\n  ( | marks the {block}-question industry opening block )")
    print(f"\n  pillars touched in those {min(show, budget)}: "
          f"{', '.join(PILLARS.get(p, '?') for p in sorted(seen_pillars))}")

    foreign = [q for q in ordered
               if (i := owned.get(q.question_id)) and not any(c.casefold() == code for c in i)]
    print(f"\n  OTHER INDUSTRIES' QUESTIONS STILL ELIGIBLE: {len(foreign)}"
          f"{'   <- should be 0' if foreign else '   OK'}")
    for q in foreign[:5]:
        print(f"     {q.question_id} [{'/'.join(sorted(owned[q.question_id]))}] "
              f"{q.question_text[:64]}")


def _safe(repo) -> bool:
    try:
        repo.question_owned_by_industry()
        return True
    except Exception:                                      # noqa: BLE001
        return False


def compare(db, codes: list[str], stage_order: int, show: int):
    """Two industries, same stage, side by side -- the headline claim."""
    sets = {}
    for c in codes:
        repo = DiagnosisRepository(db)
        engine = QuestionSelectionEngine(repo)
        founder, name, stage = _founder(db, c, stage_order)
        session = SimpleNamespace(session_id=-1, routing_state="continue",
                                  founder_industry_id=founder.industry_mapped_id,
                                  questions_answered_count=0)
        ordered = engine.order_candidates(
            engine.candidate_questions(session, founder), session, founder)
        sets[c] = (name, ordered)

    print("=" * 72)
    print(f"SAME STAGE ({stage_order}), DIFFERENT INDUSTRY")
    print("=" * 72)
    for c, (name, ordered) in sets.items():
        print(f"\n  {name} ({c}) -- first {show}:")
        for n, q in enumerate(ordered[:show], 1):
            print(f"    {n:>2}. {q.category[:20]:<20} {q.question_text[:62]}")

    a, b = codes[0], codes[1]
    ids_a = [q.question_id for q in sets[a][1][:show]]
    ids_b = [q.question_id for q in sets[b][1][:show]]
    shared = len(set(ids_a) & set(ids_b))
    verdict = ("DIFFERENT -- industry is steering selection." if shared < show
               else "IDENTICAL -- industry is NOT steering selection. Run --preflight.")
    print(f"\n  Overlap in the first {show}: {shared}/{show}")
    print(f"  {verdict}")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--industry", help="industry_code, e.g. saas")
    p.add_argument("--stage", type=int, default=6,
                   help="founder_stages.stage_order, 1-8 (default 6, Expansion)")
    p.add_argument("--show", type=int, default=20)
    p.add_argument("--compare", help="two industry codes, comma separated")
    p.add_argument("--preflight", action="store_true",
                   help="only check whether this database can run the feature")
    p.add_argument("--list-industries", action="store_true")
    args = p.parse_args()

    db = SessionLocal()
    try:
        if args.list_industries:
            for row in db.execute(text(
                    "select industry_code, industry_name from industries "
                    "order by industry_code")):
                print(f"  {row[0]:24} {row[1]}")
            return 0
        rc = preflight(db)
        if args.preflight:
            return rc
        if args.compare:
            codes = [c.strip() for c in args.compare.split(",") if c.strip()]
            if len(codes) != 2:
                sys.exit("--compare needs exactly two industry codes")
            compare(db, codes, args.stage, args.show)
        else:
            simulate(db, args.industry, args.stage, args.show)
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
