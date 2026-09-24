# -*- coding: utf-8 -*-
"""One founder, end to end, with every answer written down in advance.

WHAT THIS IS FOR. `e2e_journey_check` proves the pipeline RUNS. This proves it
runs on ONE NAMED FOUNDER whose answers a human authored and can defend --
Ayush, pre-revenue SaaS at Early Traction -- so the output can be read as a
diagnosis rather than as a smoke test.

WHY THE ANSWERS ARE IN A SEPARATE FILE AND NOT GENERATED. The point of the
exercise is that nobody tuned an answer to produce a finding. `_ayush_answers`
carries the exact text and, beside each one, the grade its author expected --
which is recorded for comparison and NEVER sent to the engine. A run where the
classifier disagrees with the author is the interesting result, and that
comparison is only possible because the expectation was written down first.

Answers deliberately span the range a real founder gives: strong where he has
done the work, weak where he has not, and N/A where the question genuinely does
not apply to him (no free tier, so the free-plan questions are not answered with
invented evidence). Reading N/A as negative evidence is one of the things this
run exists to detect.

Writes ONE founder, ONE session and ONE report into the named database, under
an @ally-e2e.local address. Nothing in the app imports this module.

    ANTHROPIC_API_KEY=... LLM_PROVIDER=anthropic ADAPTIVE_QUESTIONS=true \
    DATABASE_URL=... python -m scripts.qa.ayush_e2e

Without a key it still completes, but every answer falls back to amber and the
report is structurally complete and diagnostically empty -- see `llm_calls` in
the output, which is the number to check first.

The SECOND number to check is `contaminated`. Adaptive selection does not serve
the question set the answer bank was written against, and every question it
serves that the bank does not cover gets a placeholder that scores RED. Past
MAX_PLACEHOLDER_SHARE the diagnostic half of the run is measuring this file
rather than the engine, the summary says so, and the exit code is non-zero.
Exit 1 here does not mean the pipeline failed -- it means the numbers cannot be
quoted.
"""
from __future__ import annotations
import json, os, sys, time
from datetime import datetime, timezone

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2]))
from scripts.qa import _ayush_answers as BANK

import sqlalchemy as sa
from fastapi.testclient import TestClient

from app.api.deps import get_founder_record
from app.core.config import settings
from app.db.session import SessionLocal
from app.main import app
from app.models import Founder

OUT = os.environ.get("AYUSH_E2E_OUT", os.getcwd())
#: Served when adaptive selection picks a question the bank does not cover.
#:
#: THIS IS NOT AYUSH. It reads to the classifier as avoidance and scores RED
#: every time, so each one is a fabricated red in his diagnosis. Measured on the
#: first keyed run: 20 of 36 served questions got this, all 20 scored red, and
#: two pillars carrying 45% of the model weight scored a flat 0 on answers he
#: never gave. The headline "Critical Gap 22/100" was mostly a measurement of
#: this constant.
#:
#: Why it happens: the bank was authored against the question set adaptive
#: selection serves with ADAPTIVE_QUESTIONS=false. Turning the advisor on
#: changes which questions come, and the industry opening block forces the
#: first 12-13 out of the 1,800-question industry bank, which the bank does not
#: cover at all.
#:
#: So it exists only to keep a run moving far enough to be diagnosed. Anything
#: above MAX_PLACEHOLDER_SHARE and the run is measuring the harness -- see
#: check_contamination, which refuses to call such a run clean.
GENERIC = ("Honestly, I don't have a good answer for that yet. We're pre-revenue "
           "and a lot of that isn't built -- it's on the list, not done.")

#: Above this share of diagnosis answers, the run is not evidence about the
#: engine. Deliberately strict: every placeholder is a manufactured red, and a
#: handful is enough to flip a thinly-assessed pillar to Critical Gap. Founder
#: Readiness is scored on as few as 3 answers, so two placeholders there decide
#: a band on their own.
MAX_PLACEHOLDER_SHARE = 0.10

PROFILE = dict(
    full_name="Ayush", industry="Technology & SaaS", stage_order=4,
    business_name="Ally",
    business_description=(
        "AI-powered SaaS that helps businesses diagnose problems, identify root "
        "causes, and turn insights into actionable growth decisions."),
)


def seed(db):
    """Ayush's onboarding, as the scenario describes him. Same shape as the
    repo harness's own seeder so a scenario founder and a real one cannot
    disagree -- industry_mapped_id in particular is resolved by the same rule
    FounderRepository.resolve_industry_id applies at save time."""
    email = f"e2e+ayush{int(time.time())}@ally-e2e.local"
    fid = db.execute(sa.text("""
        insert into founders (user_id, email, full_name, stage_id, profile_completed,
                              experience_level, problem_statement, building_summary,
                              business_name, industry, industry_mapped_id,
                              customer_segment, current_challenges, goal_90_day,
                              vision_1_year, current_revenue, product_description,
                              founder_reality_signals, business_reality_signals,
                              invisible_gaps)
        values (gen_random_uuid(), :e, 'Ayush', :s, true,
                'one_company', :problem, :building, 'Ally', :industry,
                (select industry_id from industries
                  where lower(btrim(:industry)) in (lower(industry_name),
                                                    lower(industry_code))
                  order by industry_id limit 1),
                cast(:segment as jsonb), cast(:challenges as jsonb), :goal90, :vision1,
                :rev, :prod,
                cast(:freality as jsonb), cast(:breality as jsonb),
                cast(:gaps as jsonb))
        returning founder_id"""),
        {"e": email, "s": PROFILE["stage_order"],
         "industry": PROFILE["industry"],
         "problem": ("Founders often know something is wrong in their business, "
                     "but they struggle to identify the real root cause and what "
                     "they should fix first."),
         "building": ("A working AI SaaS product, now doing outbound outreach. "
                      "Early interest and feedback, no predictable acquisition "
                      "or revenue yet."),
         "segment": json.dumps(["Businesses", "Developers", "Enterprises"]),
         "challenges": json.dumps(["turning early interest into paying customers",
                                   "no repeatable acquisition process",
                                   "founder involved in everything"]),
         "goal90": "A repeatable way to get from demo to a paying customer.",
         "vision1": "Predictable acquisition and a delivery process that does "
                    "not run through me.",
         "rev": "pre_revenue",
         "prod": PROFILE["business_description"],
         # Ayush's own onboarding self-assessment, answered the way the
         # scenario describes him -- not tuned to produce a finding.
         "freality": json.dumps({
             "clear_next_priorities": True,   # he can name them: pricing, follow-up, acquisition
             "decisive": True,                # pushes to move rather than de-risk
             "effort_aligned_to_growth": False,  # built features instead of selling, by his own account
             "executes_consistently": False,     # the follow-up sequence still does not exist
             "mentally_clear": False}),          # shut down for two days three weeks ago
         "breality": json.dumps({
             "revenue_predictable": False,    # pre-revenue
             "systems_defined": False,        # processes informal
             "plans_become_execution": False, # plan lives in his head and is out of date
             "team_independent": False,       # everything customer-facing runs through him
             "financials_clear": False}),     # spreadsheet, no accounting software
         "gaps": json.dumps(["pricing"])}).scalar_one()
    db.execute(sa.text("""
        insert into founder_consents (consent_id, founder_id, terms_version,
                                      privacy_version, agree_terms, agree_diagnosis)
        values (gen_random_uuid(), :f, 'v1', 'v1', true, true)"""), {"f": fid})
    ind = db.execute(sa.text(
        "select industry from founders where founder_id=:f"), {"f": fid}).scalar()
    db.commit()
    return fid, email, ind


def answer_for(phase, qid, text):
    if phase == "dna":
        a = BANK.FOUNDER_DNA.get(qid)
        return (a, "bank", "n/a") if a else (GENERIC, "generic", "n/a")
    src = BANK.CURRENT_PROBLEM if phase == "cp" else BANK.DIAGNOSIS
    hit = src.get(qid)
    if hit:
        return hit[0], "bank", hit[1]
    return GENERIC, "generic", "unknown"


def walk(client, start, ans_path, id_field, phase, out):
    r = client.post(start)
    if r.status_code not in (200, 201):
        raise SystemExit(f"{start} -> {r.status_code} {r.text[:300]}")
    q = (r.json() or {}).get("question")
    guard = 0
    while q and guard < 120:
        guard += 1
        qid = q.get(id_field)
        a, src, grade = answer_for(phase, qid, q.get("question_text", ""))
        rec = {"phase": phase, "question_id": qid,
               "question_code": q.get("question_code"),
               "question_text": q.get("question_text"),
               "category": q.get("category"),
               "dimension_code": q.get("dimension_code"),
               "question_type": q.get("question_type"),
               "difficulty_level": q.get("difficulty_level"),
               "answer": a, "answer_source": src, "my_grade": grade}
        resp = client.post(ans_path, json={id_field: qid, "answer_text": a})
        if resp.status_code not in (200, 201):
            raise SystemExit(f"{ans_path} -> {resp.status_code} {resp.text[:300]}")
        data = resp.json() or {}
        if data.get("accepted") is False:
            rec["rejected_as_off_question"] = True
            out.append(rec)
            q = data.get("next_question")
            continue
        rec["progress"] = data.get("progress")
        out.append(rec)
        q = data.get("next_question")
    return out


def check_contamination(transcript, labels):
    """(clean, lines). Whether this run is evidence about the ENGINE.

    A placeholder is not a weak answer, it is an absent one, and the classifier
    reads it as avoidance -- so every one is a red that Ayush did not earn. Past
    a threshold the pillar scores, the root-cause ranking and the headline band
    are measuring this file rather than the diagnosis engine.

    `e2e_journey_check` has had this guard since its QuestionKeyedLedger; this
    script shipped without it, reported `err=None` over 20 placeholders, and a
    whole keyed run had to be thrown away before anyone noticed. Hence: printed
    on every run, in the summary line, whether or not it fails.
    """
    diag = [r for r in transcript if r["phase"] == "diag"]
    if not diag:
        return True, ["no diagnosis questions served"]

    placeholders = [r for r in diag if r["answer_source"] == "generic"]
    share = len(placeholders) / len(diag)
    lines = [f"  placeholders: {len(placeholders)}/{len(diag)} diagnosis answers "
             f"({share:.0%}) were NOT Ayush's words"]

    if placeholders:
        reds = sum(1 for r in placeholders if labels.get(r["question_id"]) == "red")
        total_red = sum(1 for lab in labels.values() if lab == "red")
        lines.append(f"  of those, {reds} scored red; {total_red} red labels in "
                     f"the whole run, so {reds} of {total_red} are harness "
                     "artifacts, not findings")
        by_cat: dict[str, int] = {}
        for r in placeholders:
            by_cat[r.get("category") or "?"] = by_cat.get(r.get("category") or "?", 0) + 1
        worst = sorted(by_cat.items(), key=lambda kv: -kv[1])[:4]
        lines.append("  concentrated in: "
                     + ", ".join(f"{c} x{n}" for c, n in worst))

    if share <= MAX_PLACEHOLDER_SHARE:
        return True, lines

    lines += [
        "",
        f"  CONTAMINATED -- above the {MAX_PLACEHOLDER_SHARE:.0%} threshold.",
        "  The structural results (stage band, industry targeting, duplicates,",
        "  session isolation, completion) are still valid: they do not depend on",
        "  what was answered. Everything DIAGNOSTIC is not -- pillar scores,",
        "  root-cause ranking, the top 3, business health, the report's verdict.",
        "  Do not quote those numbers.",
        "",
        "  Fix by extending _ayush_answers to the questions adaptive selection",
        "  actually serves. result.json lists every one under answer_source",
        "  'generic'; each needs an answer Ayush would really give.",
    ]
    return False, lines


def main():
    started = datetime.now(timezone.utc).isoformat()
    with SessionLocal() as db:
        fid, email, ind = seed(db)
        calls_before = db.execute(sa.text("select count(*) from llm_call_log")).scalar()

    app.dependency_overrides[get_founder_record] = lambda: None
    from fastapi import Depends
    from sqlalchemy.orm import Session as S
    from app.db.session import get_db

    def _f(db: S = Depends(get_db)):
        return db.get(Founder, fid)
    app.dependency_overrides[get_founder_record] = _f
    from app.api.v1.diagnosis.router import answer_rate_limit, start_rate_limit
    app.dependency_overrides[start_rate_limit] = lambda: None
    app.dependency_overrides[answer_rate_limit] = lambda: None

    client = TestClient(app)
    transcript = []
    walk(client, "/api/v1/founder-dna/start", "/api/v1/founder-dna/answer",
         "founder_dna_question_id", "dna", transcript)
    walk(client, "/api/v1/current-problem/start", "/api/v1/current-problem/answer",
         "current_problem_question_id", "cp", transcript)
    walk(client, "/api/v1/diagnosis/start", "/api/v1/diagnosis/answer",
         "question_id", "diag", transcript)

    err = None
    with SessionLocal() as db:
        founder = db.get(Founder, fid)
        sid = db.execute(sa.text(
            "select session_id from sessions where founder_id=:f "
            "order by session_id desc limit 1"), {"f": fid}).scalar()
        try:
            from app.api.v1.reasoning.trigger import build_reasoning_service, run_sync
            run_sync(build_reasoning_service(db).analyze_session(founder, sid))
            db.commit()
        except Exception as exc:
            err = f"{type(exc).__name__}: {exc}"
            db.rollback()

    with SessionLocal() as db:
        labels = {qid: lab for qid, lab in db.execute(sa.text(
            "select question_id, score_label from answers where founder_id=:f"),
            {"f": fid})}
        session_row = db.execute(sa.text(
            "select questions_answered_count, routing_state, "
            "overall_confidence_score, completed_at from sessions "
            "where session_id=:s"), {"s": sid}).first()
        rcs = [dict(r._mapping) for r in db.execute(sa.text(
            "select * from detected_root_causes where session_id=:s"), {"s": sid})]
        rep = db.execute(sa.text(
            "select * from founder_reports where founder_id=:f "
            "order by report_id desc limit 1"), {"f": fid}).first()
        calls_after, cost = db.execute(sa.text(
            "select count(*), coalesce(sum(estimated_cost_usd),0) from llm_call_log")).one()
        call_breakdown = [dict(r._mapping) for r in db.execute(sa.text(
            "select task, provider, model_id, status, count(*) n, coalesce(sum(estimated_cost_usd),0) cost, coalesce(sum(input_tokens),0) tin, coalesce(sum(output_tokens),0) tout "
            "from llm_call_log group by 1,2,3,4 order by n desc"))]

    for rec in transcript:
        if rec["phase"] == "diag":
            rec["score_label"] = labels.get(rec["question_id"])

    payload = {
        "started_at": started,
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "founder_id": fid, "founder_email": email, "industry": ind,
        "session_id": sid,
        "session": dict(session_row._mapping) if session_row else None,
        "transcript": transcript,
        "detected_root_causes": rcs,
        "report": dict(rep._mapping) if rep else None,
        "llm_calls": calls_after - calls_before,
        "llm_cost_usd": float(cost),
        "llm_call_breakdown": call_breakdown,
        "reasoning_error": err,
        "config": {
            "ADAPTIVE_QUESTIONS": settings.ADAPTIVE_QUESTIONS,
            "ANSWER_CLASSIFIER": settings.ANSWER_CLASSIFIER,
            "LLM_PROVIDER": settings.LLM_PROVIDER,
            "anthropic_key_present": bool(settings.ANTHROPIC_API_KEY),
        },
    }
    # Written AFTER the contamination verdict, so `contaminated` is in the file
    # a reader opens rather than something they have to recompute.
    clean, contamination = check_contamination(transcript, labels)
    payload["contaminated"] = not clean
    with open(os.path.join(OUT, "result.json"), "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=1, default=str)

    print(f"founder={fid} session={sid} questions={len(transcript)} "
          f"llm_calls={payload['llm_calls']} cost=${payload['llm_cost_usd']:.4f} "
          f"root_causes={len(rcs)} report={'yes' if rep else 'NO'} err={err} "
          f"contaminated={'YES' if not clean else 'no'}")
    print("\n".join(contamination))
    # Non-zero so CI and a human skimming the tail both see it. The run still
    # completed and result.json is still written -- the exit code says the
    # numbers cannot be trusted, not that the pipeline failed.
    return 0 if clean else 1


if __name__ == "__main__":
    sys.exit(main())
