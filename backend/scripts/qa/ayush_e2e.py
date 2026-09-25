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
#: Above this share of substituted answers the run is not evidence -- see the
#: block at the end of main(). A third is generous: the adaptive selector will
#: legitimately pick some questions the bank does not cover, but past this the
#: bands are the placeholder's, not the founder's.
GENERIC_LIMIT = 1 / 3

GENERIC = ("Honestly, I don't have a good answer for that yet. We're pre-revenue "
           "and a lot of that isn't built -- it's on the list, not done.")

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

    # Counted from the transcript rather than tallied as we go, so a question
    # that was re-asked after an off-question rejection is not double counted.
    _substituted = sum(1 for r in transcript if r.get("answer_source") == "generic")
    _from_bank = sum(1 for r in transcript if r.get("answer_source") == "bank")

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
        # SUBSTITUTION ACCOUNTING. See the GENERIC_LIMIT block below: a run that
        # answered most questions with the placeholder is measuring the harness,
        # so the count belongs in the summary and not only in the transcript.
        "answers_from_bank": _from_bank,
        "answers_substituted": _substituted,
        "substituted_share": round(_substituted / max(len(transcript), 1), 3),
        "config": {
            "ADAPTIVE_QUESTIONS": settings.ADAPTIVE_QUESTIONS,
            "ANSWER_CLASSIFIER": settings.ANSWER_CLASSIFIER,
            "LLM_PROVIDER": settings.LLM_PROVIDER,
            "anthropic_key_present": bool(settings.ANTHROPIC_API_KEY),
        },
    }
    with open(os.path.join(OUT, "result.json"), "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=1, default=str)
    print(f"founder={fid} session={sid} questions={len(transcript)} "
          f"answered_from_bank={_from_bank} SUBSTITUTED={_substituted} "
          f"({payload['substituted_share']:.0%}) "
          f"llm_calls={payload['llm_calls']} cost=${payload['llm_cost_usd']:.4f} "
          f"root_causes={len(rcs)} report={'yes' if rep else 'NO'} err={err}")

    # WHY THIS EXITS NON-ZERO.
    #
    # answer_for() substitutes GENERIC for any question the answer bank does not
    # cover. That is the right behaviour -- refusing to answer would abort the
    # walk -- but it used to be invisible: the summary line read
    # "questions=58 llm_calls=50 ... report=yes err=None" on a run where TWENTY
    # of thirty-six diagnosis questions were the placeholder. The placeholder is
    # a non-answer, so the classifier scored all of them Red, and two pillars --
    # Founder Readiness at 25% of the model and Revenue Maturity at 20% --
    # scored a flat 0 entirely on answers the founder never gave. The run then
    # reported a confident "Critical Gap, 22/100" that was measuring this script.
    #
    # The adaptive selector picks questions the bank was not written against, so
    # a few misses are expected and fine. A majority is not a run, it is noise,
    # and it must not exit 0 and look like evidence.
    # WHY THIS ALSO EXITS NON-ZERO.
    #
    # The module docstring has always said that without a key "every answer
    # falls back to amber and the report is structurally complete and
    # diagnostically empty". Nothing enforced it. So a run with no key printed
    #
    #     questions=52 answered_from_bank=50 SUBSTITUTED=2 (4%) llm_calls=0
    #     root_causes=8 report=yes err=None
    #
    # and exited 0 -- and I read that as evidence that the new industry content
    # was being detected from the founder's answers. It was not. All thirty
    # answers carried the same amber fallback, so the ranking underneath came
    # from category risk and stage weights alone; not one word Ayush wrote
    # influenced it. `llm_calls=0` was right there in the line and said exactly
    # this, which is the problem with putting the disqualifying fact in the
    # middle of a summary that otherwise reads like success.
    #
    # scripts/e2e_journey_check.py refuses to start in this configuration and
    # says why. This is the same refusal, applied after the walk so the
    # structural result is still written to result.json and can be read
    # deliberately -- just never mistaken for a diagnosis.
    labels = {r.get("score_label") for r in transcript if r.get("score_label")}
    unscored_run = payload["llm_calls"] == 0 and len(labels) <= 1
    if unscored_run and os.environ.get("AYUSH_E2E_ALLOW_UNSCORED") != "1":
        print(f"\nFAIL: no answer was actually classified. llm_calls=0 and every "
              f"answer carries the same band ({', '.join(sorted(labels)) or 'none'}).\n"
              f"      This run proves the pipeline CONNECTS. It proves nothing "
              f"about classification, detection or ranking:\n"
              f"      the bands are a fallback, so the root causes and pillar "
              f"scores below are not reading the founder's answers.\n"
              f"      For a real run: ANTHROPIC_API_KEY=... LLM_PROVIDER=anthropic "
              f"ADAPTIVE_QUESTIONS=true\n"
              f"      To accept a structural-only run on purpose, set "
              f"AYUSH_E2E_ALLOW_UNSCORED=1 -- and do not call the result a "
              f"diagnosis.")
        raise SystemExit(3)

    if payload["substituted_share"] > GENERIC_LIMIT:
        print(f"\nFAIL: {_substituted} of {len(transcript)} answers were the "
              f"placeholder, not the founder's ({payload['substituted_share']:.0%} "
              f"> {GENERIC_LIMIT:.0%} limit).\n"
              f"      The bands, pillar scores and root causes in this run are "
              f"measuring the harness.\n"
              f"      Add answers for the missed question ids in "
              f"scripts/qa/_ayush_answers.py, then re-run.\n"
              f"      Missed ids: "
              + ", ".join(str(r["question_id"]) for r in transcript
                          if r.get("answer_source") == "generic"))
        raise SystemExit(2)


if __name__ == "__main__":
    main()
