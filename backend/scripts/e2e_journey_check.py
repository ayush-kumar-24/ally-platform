"""Walk one founder through the whole journey and report what actually happened.

Onboarding -> Founder DNA -> Current Problem -> Diagnosis -> Report, over the
real HTTP API, against a real database, with whatever LLM configuration the
environment carries. Nothing is stubbed except authentication, which is
overridden because there is no browser here to log in with.

WHY THIS EXISTS. The unit suite covers the engines in isolation and never calls
a model. This is the other half: it proves the phases connect, that the gates
fire in the right order, and -- when a key is configured -- that the model is
genuinely being called rather than silently falling back to MockLLMProvider.
That last one is the point. `llm_call_log` is counted before and after, so a
run that produces plausible-looking output on a dead key is caught rather than
believed.

    python -m scripts.e2e_journey_check --database-url "postgresql+psycopg2://..." --confirm-writes
    python -m scripts.e2e_journey_check --database-url "..." --stage 5 --confirm-writes
    python -m scripts.e2e_journey_check --database-url "..." --cleanup

IT WRITES. A founder, a Founder DNA run, a Current Problem run, a diagnosis
session, its answers, and a report. Every founder it creates is named
`e2e+<timestamp>@ally-e2e.local`, and `--cleanup` deletes every founder at that
domain and everything cascading from them. The database URL must be passed
explicitly -- it deliberately does NOT read DATABASE_URL, so pointing this at
production has to be a decision rather than an accident. `--confirm-writes` is
required on top of that.

COST. A full diagnosis is roughly one model call per question plus the
reasoning pipeline. The repository's own estimate is about Rs 14-15 per run;
this prints the measured cost from `llm_call_log` at the end, so you can check
that against reality rather than trusting the estimate.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone

TEST_DOMAIN = "ally-e2e.local"

#: Answers with enough substance for a classifier to have an opinion. A run
#: answering "test" to everything tells you the plumbing works and nothing
#: about whether the scoring does.
ANSWERS = [
    "We have about ten paying customers, mostly from my own network, and two "
    "churned last month without telling me why.",
    "Honestly I spend most of the week firefighting support and very little on "
    "anything that compounds.",
    "I have never sat down and worked out the real size of this market. I know "
    "the problem is real because I had it myself.",
    "The last thing I shipped took six weeks and almost nobody has used it. I "
    "built it because one loud customer asked.",
    "I do not really know why we charge what we charge. I copied a competitor's "
    "pricing page when we launched and never revisited it.",
    "There are two of us. Neither of us owns anything in writing, we just work "
    "out who does what each morning.",
]


def _answer_for(n: int) -> str:
    return ANSWERS[n % len(ANSWERS)]


# ---------------------------------------------------------------------------


def _config_report(settings) -> tuple[list[str], bool]:
    lines = [
        f"  LLM_PROVIDER          {settings.LLM_PROVIDER or '(empty)'}",
        f"  ANTHROPIC_API_KEY     {'present' if settings.ANTHROPIC_API_KEY else 'MISSING'}",
        f"  OPENAI_API_KEY        {'present' if settings.OPENAI_API_KEY else 'missing'}",
        f"  ADAPTIVE_QUESTIONS    {settings.ADAPTIVE_QUESTIONS}",
        f"  ANSWER_CLASSIFIER     {settings.ANSWER_CLASSIFIER}",
        f"  scoring configured    {settings.diagnosis_scoring_configured}",
    ]
    return lines, bool(settings.diagnosis_scoring_configured)


def _llm_calls(db, sa) -> tuple[int, float]:
    """(calls, cost so far). Zero rows after a run means the model never ran."""
    try:
        row = db.execute(sa.text(
            "select count(*), coalesce(sum(estimated_cost_usd), 0) from llm_call_log"
        )).one()
        return int(row[0]), float(row[1])
    except Exception:                                            # noqa: BLE001
        db.rollback()
        return -1, 0.0


def cleanup(db, sa) -> int:
    founders = [r[0] for r in db.execute(sa.text(
        "select founder_id from founders where email like :p"),
        {"p": f"%@{TEST_DOMAIN}"}).all()]
    if not founders:
        print(f"  nothing to clean up at @{TEST_DOMAIN}")
        return 0
    for table, col in (
        ("answers", "founder_id"), ("founder_dna_answers", "founder_id"),
        ("current_problem_answers", "founder_id"), ("founder_reports", "founder_id"),
        ("detected_root_causes", "session_id"), ("sessions", "founder_id"),
        ("founder_consents", "founder_id"),
    ):
        try:
            if col == "session_id":
                db.execute(sa.text(
                    f"delete from {table} where session_id in "
                    "(select session_id from sessions where founder_id = any(:f))"),
                    {"f": founders})
            else:
                db.execute(sa.text(f"delete from {table} where {col} = any(:f)"),
                           {"f": founders})
        except Exception:                                        # noqa: BLE001
            db.rollback()  # table may not exist on this schema; keep going
    db.execute(sa.text("delete from founders where founder_id = any(:f)"), {"f": founders})
    db.commit()
    print(f"  removed {len(founders)} test founder(s) and their data")
    return len(founders)


def _seed_founder(db, sa, stage_order: int) -> tuple[int, str]:
    email = f"e2e+{int(time.time())}@{TEST_DOMAIN}"
    fid = db.execute(sa.text("""
        insert into founders (user_id, email, full_name, stage_id, profile_completed,
                              experience_level, problem_statement, building_summary,
                              business_name, industry, customer_segment,
                              current_challenges, goal_90_day, vision_1_year,
                              founder_reality_signals, invisible_gaps)
        values (gen_random_uuid(), :e, 'E2E Test Founder', :s, true,
                'one_company',
                'Customers churn after the second month and I cannot tell why.',
                'Compliance SaaS for Indian SMBs.',
                'Acme Compliance', 'SaaS',
                '["Business"]'::jsonb, '["Sales","Cash flow"]'::jsonb,
                'Ten real customer interviews.', 'Series A raised.',
                '{"clear_next_step": true}'::jsonb, '["pricing"]'::jsonb)
        returning founder_id"""), {"e": email, "s": stage_order}).scalar_one()
    db.execute(sa.text("""
        insert into founder_consents (consent_id, founder_id, terms_version,
                                      privacy_version, agree_terms, agree_diagnosis)
        values (gen_random_uuid(), :f, 'v1', 'v1', true, true)"""), {"f": fid})
    db.commit()
    return fid, email


def _walk(client, start_path, answer_path, id_field, label, out):
    """Drive one question/answer phase to completion, recording every question."""
    r = client.post(start_path)
    if r.status_code not in (200, 201):
        print(f"  FAIL {start_path} -> {r.status_code} {r.text[:200]}")
        return False
    q = (r.json() or {}).get("question")
    reprompts = 0
    while q:
        out.append(q)
        n = len(out)
        body = {id_field: q[id_field], "answer_text": _answer_for(n)}
        a = client.post(answer_path, json=body)
        if a.status_code not in (200, 201):
            print(f"  FAIL {answer_path} -> {a.status_code} {a.text[:200]}")
            return False
        data = a.json() or {}
        if data.get("accepted") is False:
            # Only the LLM path rejects an answer as off-question, so seeing one
            # is itself evidence the model ran.
            reprompts += 1
            out.pop()
            if reprompts > 3:
                print("  FAIL too many reprompts in a row")
                return False
            continue
        reprompts = 0
        if data.get("is_complete") or (data.get("progress") or {}).get("is_complete"):
            q = data.get("next_question")
            if not q:
                break
        q = data.get("next_question")
    print(f"  {label}: {len(out)} question(s) answered")
    return True


def run(args) -> int:
    os.environ["DATABASE_URL"] = args.database_url
    os.environ.setdefault("SECRET_KEY", "e2e-journey-check-not-a-real-secret")

    import sqlalchemy as sa
    from fastapi.testclient import TestClient

    from app.api.deps import get_founder_record
    from app.core.config import settings
    from app.db.session import SessionLocal, get_db
    from app.main import app
    from app.models import Founder

    # Cleanup first, and before the scoring check. Tidying up after a run must
    # not require a working model config -- that would strand test rows on any
    # machine without a key, which is exactly where they get left behind.
    if args.cleanup:
        print("CLEANUP")
        with SessionLocal() as db:
            cleanup(db, sa)
        return 0

    print("=" * 74)
    print("CONFIGURATION")
    print("=" * 74)
    lines, scoring_on = _config_report(settings)
    print("\n".join(lines))
    if not scoring_on and not args.allow_unscored:
        print("\n  ABORT: scoring is not configured, so every answer would be "
              "recorded as a flat amber and no report would be produced.\n"
              "  Set ADAPTIVE_QUESTIONS=true (with a working key), or pass "
              "--allow-unscored to run anyway.")
        return 2

    with SessionLocal() as db:
        calls_before, cost_before = _llm_calls(db, sa)
        fid, email = _seed_founder(db, sa, args.stage)
        print(f"\n  test founder {fid} <{email}> at stage_order {args.stage}")

    from fastapi import Depends
    from sqlalchemy.orm import Session as OrmSession

    def _founder(db: OrmSession = Depends(get_db)):
        return db.get(Founder, fid)

    app.dependency_overrides[get_founder_record] = _founder
    client = TestClient(app)

    dna, problem, diagnosis = [], [], []
    print("\n" + "=" * 74)
    print("JOURNEY")
    print("=" * 74)
    ok = (
        _walk(client, "/api/v1/founder-dna/start", "/api/v1/founder-dna/answer",
              "founder_dna_question_id", "Founder DNA", dna)
        and _walk(client, "/api/v1/current-problem/start",
                  "/api/v1/current-problem/answer",
                  "current_problem_question_id", "Current Problem", problem)
        and _walk(client, "/api/v1/diagnosis/start", "/api/v1/diagnosis/answer",
                  "question_id", "Diagnosis", diagnosis)
    )
    if not ok:
        return 1

    # --- report -----------------------------------------------------------
    report = None
    with SessionLocal() as db:
        founder = db.get(Founder, fid)
        sid = db.execute(sa.text(
            "select session_id from sessions where founder_id=:f "
            "order by session_id desc limit 1"), {"f": fid}).scalar()
        try:
            from app.api.v1.reasoning.trigger import build_reasoning_service, run_sync
            run_sync(build_reasoning_service(db).analyze_session(founder, sid))
            db.commit()
        except Exception as exc:                                 # noqa: BLE001
            print(f"\n  reasoning pipeline raised: {type(exc).__name__}: {exc}")
            db.rollback()
        report = db.execute(sa.text(
            "select report_id, business_dna from founder_reports "
            "where founder_id=:f order by report_id desc limit 1"), {"f": fid}).first()
        calls_after, cost_after = _llm_calls(db, sa)

    # --- what happened ----------------------------------------------------
    print("\n" + "=" * 74)
    print("QUESTIONS SERVED")
    print("=" * 74)
    print("\n-- Founder DNA --")
    for i, q in enumerate(dna, 1):
        close = "  [WOW CLOSE]" if q.get("is_closing") else ""
        print(f"  {i:2d}. ({q.get('dimension_code')}/{q.get('format')}){close}")
        print(f"      {q.get('question_text','')}")
    print("\n-- Current Problem --")
    for i, q in enumerate(problem, 1):
        print(f"  {i:2d}. {q.get('question_text','')}")
    print("\n-- Diagnosis --")
    for i, q in enumerate(diagnosis, 1):
        print(f"  {i:2d}. [{q.get('category')}] {q.get('question_text','')}")

    print("\n" + "=" * 74)
    print("RESULT")
    print("=" * 74)
    with SessionLocal() as db:
        bands = db.execute(sa.text(
            "select score_label, count(*) from answers where founder_id=:f "
            "group by 1 order by 2 desc"), {"f": fid}).all()
    print(f"  answer bands            {dict(bands) or 'none'}")
    if len(bands) == 1 and bands[0][0] == "amber":
        print("    ^ every answer identical -- this is the unscored fallback, "
              "not a real classification")

    if report:
        bd = report[1] or {}
        print(f"  report                  #{report[0]} generated")
        print(f"  overall band            {bd.get('band')}")
        print(f"  pillars assessed        {bd.get('pillars_assessed')}"
              f" of {bd.get('pillars_total')}"
              f"  ({bd.get('assessed_weight_pct')}% of the model)")
        for p in (bd.get("pillars") or []):
            cov = p.get("dimensions_in_scope") or []
            tot = p.get("dimensions_total") or 0
            qual = f"  ({', '.join(cov)} only)" if cov and tot and len(cov) < tot else ""
            print(f"    {p.get('pillar_name')}{qual}: {p.get('band') or 'not assessed'}")
    else:
        print("  report                  NONE GENERATED")

    if calls_before >= 0:
        made = calls_after - calls_before
        print(f"  model calls this run    {made}"
              f"   (cost ${cost_after - cost_before:.4f})")
        if made == 0:
            print("    ^ ZERO. Nothing reached a model. Either scoring is off, or "
                  "the provider failed and the failover chain fell through to "
                  "MockLLMProvider -- check the logs for an auth error.")
    else:
        print("  model calls this run    (llm_call_log unavailable)")

    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as fh:
            json.dump({"generated_at": datetime.now(timezone.utc).isoformat(),
                       "stage_order": args.stage, "founder_id": fid,
                       "founder_dna": dna, "current_problem": problem,
                       "diagnosis": diagnosis,
                       "report": (report[1] if report else None)}, fh, indent=1)
        print(f"\n  written to {args.json_out}")

    print(f"\n  clean up with: --database-url ... --cleanup")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--database-url", required=True,
                   help="SQLAlchemy URL. Deliberately NOT read from DATABASE_URL -- "
                        "this script writes, so the target has to be named.")
    p.add_argument("--stage", type=int, default=1, choices=range(1, 9),
                   help="founder_stages.stage_order to test as (default 1, Ideation)")
    p.add_argument("--confirm-writes", action="store_true",
                   help="required: acknowledges that this creates a founder, a "
                        "diagnosis and a report in the named database")
    p.add_argument("--cleanup", action="store_true",
                   help=f"delete every @{TEST_DOMAIN} founder and their data, then exit")
    p.add_argument("--allow-unscored", action="store_true",
                   help="run even with scoring off (useful only to test the fallback)")
    p.add_argument("--json-out", metavar="FILE", help="write the full transcript as JSON")
    args = p.parse_args(argv)

    if not args.confirm_writes and not args.cleanup:
        p.error("--confirm-writes is required (or --cleanup)")
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
