"""Pre-generate a persona's answer to EVERY question it could be asked.

THE PROBLEM. `e2e_journey_check.py --answer-map` looks answers up by
question_id, and the maps were written against a run where question selection
was deterministic. With ADAPTIVE_QUESTIONS=true the served ids depend on the
answers, so a map built from one run covers almost none of the next: measured,
7 of the first 10 questions of a re-run had no entry. Every one of those became
a literal "[HARNESS_MISS: no answer prepared for this question]" submitted as
the founder's words, scored, and carried into the diagnosis as evidence.

The persona bank has the same problem from the other side. It answers the
handful of questions it was written for and falls back to a topic-neutral line
for the rest -- deliberately, because quality is the variable under test and
subject is not. Measured across this session's runs, 65-90% of every persona
run was that fallback. Those runs establish that the engine RUNS. They cannot
establish that it diagnoses correctly, because the founder never said anything
specific.

THE FIX. Generate the persona's answer to every question in its stage's pool,
once, and cache it. Then every run is a full-coverage lookup: zero misses, zero
fallbacks, no model call at answer time, and the same founder answering the same
question the same way on every run -- so two runs differ only where the ENGINE
chose differently.

Cost is paid once per (persona, stage) and then never again. The cache is
resumable: interrupt it and re-run, and it continues from where it stopped.

    python -m scripts.qa.build_persona_answer_map \\
        --database-url "postgresql+psycopg://..." --persona weak_traction \\
        --stage 4 --out /tmp/persona_weak_traction_s4.json

Then:

    python scripts/e2e_journey_check.py --database-url "..." --stage 4 \\
        --answer-map /tmp/persona_weak_traction_s4.json --strict-evidence \\
        --confirm-writes

WHAT THIS DOES NOT DO. It does not judge the answers. A generated answer is
still a generated answer: it is consistent, specific and in character, which is
what the harness lacked, but a persona brief is not a real founder. It makes
diagnostic-accuracy testing POSSIBLE; it does not by itself make it valid.
Review a sample before quoting results built on it.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


#: What each persona is, in enough detail that an answer to ANY question is
#: determined by the brief rather than invented per question. Keep these
#: factual and specific -- numbers, dates, names of things -- because the
#: whole point is that the founder says something a diagnosis can bite on.
PERSONAS = {
    "weak_traction": """You are Ravi, founder of a B2B invoicing tool in Pune, 14 months old.
Facts you must stay consistent with:
- 60 paying customers, all on the same ₹1,200/month plan, no tiers.
- Revenue ₹72,000/month, flat for five months. Churn roughly 4 a month, replaced by 4 new.
- You have never run a pricing experiment and have never interviewed a churned customer.
- Two employees: one developer, one support person you hired three months ago.
- You personally do all sales, all onboarding calls, and approve every refund.
- No CRM. Deals live in a WhatsApp group and a spreadsheet you update on Sundays.
- You track signups and MRR. You do not track activation, cohort retention, or CAC.
- You believe the problem is "not enough leads" and have not tested that belief.
You answer briefly and honestly, admit what you have not done, and do not
volunteer plans you have not started. When you do not know a number, say so and
say what you would have to check.""",

    "traction": """You are Meera, founder of a logistics SaaS in Bangalore, 3 years old.
Facts you must stay consistent with:
- 240 paying customers on three tiers; ₹38 lakh MRR; 7% month-on-month growth.
- Net revenue retention 112%. Logo churn 1.4%/month, measured by cohort monthly.
- Sales team of four with a written qualification checklist; you review the pipeline weekly.
- You interviewed 22 churned customers last year and changed onboarding because of it.
- CAC ₹64,000, payback 11 months, tracked in a dashboard the whole team sees.
- Weakness you are honest about: you are the only one who can price a non-standard deal,
  and your top two customers are 19% of revenue.
You answer with specifics and numbers, name the system or document where something
lives, and are equally specific about the two things you have NOT solved.""",

    "strong": """You are Arjun, founder of a manufacturing-analytics company, 6 years old, 40 staff.
Facts you must stay consistent with:
- ₹9 crore ARR, 22% growth, profitable for 9 quarters.
- Four managers who each own a P&L line and hire for their own teams without your approval.
- Quarterly OKRs, a written decision-rights matrix, a documented incident process.
- You review a one-page management dashboard weekly and have not approved an
  individual refund in two years.
- Weakness you are honest about: succession -- no named successor for two of the four
  manager roles, and you still personally own the top-ten customer relationships.
You answer with the specific mechanism and where it is written down, and you
name the two gaps plainly rather than claiming everything is handled.""",
}

#: The stage-question pool the adaptive engine can draw from, by stage_order.
#: Matches `questions.primary_stage_group`, which is what the stage scope filter
#: reads -- not a guess at what the engine "probably" asks.
STAGE_GROUP = {
    1: "Stage 0", 2: "Stage 0→1", 3: "Stage 0→1", 4: "Stage 0→1",
    5: "Stage 1→10+", 6: "Stage 1→10+", 7: "Stage 1→10+", 8: "Stage 1→10+",
}

_SYSTEM = """You are role-playing a startup founder answering a diagnostic question.
Answer ONLY as the founder, in first person, 1-3 sentences, in their voice.
Never mention that you are an AI, never restate the question, never give advice.
Stay strictly consistent with the brief -- if the brief does not cover something,
answer in a way that follows from it rather than inventing a new capability.
If the founder would not know, say so plainly in their voice."""


def _questions(db, sa, stage: int):
    group = STAGE_GROUP[stage]
    rows = db.execute(sa.text(
        "select question_id, question_text from questions "
        "where primary_stage_group = :g order by question_id"), {"g": group}).all()
    dna = db.execute(sa.text(
        "select founder_dna_question_id, question_text from founder_dna_questions "
        "order by 1")).all()
    cp = db.execute(sa.text(
        "select current_problem_question_id, question_text from current_problem_questions "
        "order by 1")).all()
    return {"diag": rows, "dna": dna, "cp": cp}


def _load(path: Path) -> dict:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"dna": {}, "cp": {}, "diag": {}}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--database-url", required=True)
    p.add_argument("--persona", required=True, choices=sorted(PERSONAS))
    p.add_argument("--stage", type=int, required=True, choices=range(1, 9))
    p.add_argument("--out", required=True)
    p.add_argument("--model", default="claude-sonnet-5")
    p.add_argument("--limit", type=int, default=0,
                   help="stop after N new answers (for a costed trial run)")
    p.add_argument("--only-missing-from", metavar="RUN_JSON", action="append",
                   default=[],
                   help="Generate ONLY the question ids these previous runs "
                        "actually served but had no answer for. Repeatable. The "
                        "cheap path: a full pool is ~2,000 questions but a "
                        "session asks 30, so seeding from real runs and filling "
                        "the misses converges in a few rounds at a fraction of "
                        "the cost. Use the full pool only when you need a map "
                        "that can never miss.")
    p.add_argument("--dry-run", action="store_true",
                   help="report coverage and what it would cost; call no model")
    args = p.parse_args(argv)

    os.environ["DATABASE_URL"] = args.database_url
    import sqlalchemy as sa
    from app.db.session import SessionLocal

    out = Path(args.out)
    doc = _load(out)

    with SessionLocal() as db:
        pools = _questions(db, sa, args.stage)

    wanted = None
    if args.only_missing_from:
        wanted = {"dna": set(), "cp": set(), "diag": set()}
        for path in args.only_missing_from:
            run = json.loads(Path(path).read_text(encoding="utf-8"))
            # Each phase names its id column differently in the run file.
            for phase, key, idcol in (
                ("dna", "founder_dna", "founder_dna_question_id"),
                ("cp", "current_problem", "current_problem_question_id"),
                ("diag", "diagnosis", "question_id"),
            ):
                for item in run.get(key) or []:
                    qid = item.get(idcol) if isinstance(item, dict) else None
                    if qid is not None:
                        wanted[phase].add(str(qid))
        print("ids served by those runs: "
              + ", ".join(f"{k}={len(v)}" for k, v in wanted.items()))

    todo = [(phase, qid, text)
            for phase, rows in pools.items()
            for qid, text in rows
            if str(qid) not in doc.get(phase, {})
            and (wanted is None or str(qid) in wanted[phase])]

    have = sum(len(doc.get(k, {})) for k in ("dna", "cp", "diag"))
    total = sum(len(v) for v in pools.values())
    print(f"persona {args.persona}  stage {args.stage}  "
          f"pool {total}  cached {have}  to generate {len(todo)}")

    if args.dry_run:
        print("dry run: no model called. Re-run without --dry-run to generate.")
        return 0

    from anthropic import Anthropic
    client = Anthropic()
    brief = PERSONAS[args.persona]

    done = 0
    for phase, qid, text in todo:
        if args.limit and done >= args.limit:
            print(f"stopped at --limit {args.limit}")
            break
        try:
            msg = client.messages.create(
                model=args.model, max_tokens=300,
                system=_SYSTEM + "\n\nFOUNDER BRIEF:\n" + brief,
                messages=[{"role": "user", "content": text}],
            )
            answer = msg.content[0].text.strip()
        except Exception as exc:                                 # noqa: BLE001
            # Write what we have and stop: a partial cache is resumable, a cache
            # silently holding an error string is not.
            out.write_text(json.dumps(doc, indent=1), encoding="utf-8")
            print(f"\nSTOPPED on {phase}/{qid}: {exc}")
            print(f"wrote {have + done} cached answers to {out}; re-run to resume.")
            return 1
        doc.setdefault(phase, {})[str(qid)] = {"a": answer, "status": "answered"}
        done += 1
        if done % 25 == 0:
            out.write_text(json.dumps(doc, indent=1), encoding="utf-8")
            print(f"  {done}/{len(todo)}")

    out.write_text(json.dumps(doc, indent=1), encoding="utf-8")
    covered = sum(len(doc.get(k, {})) for k in ("dna", "cp", "diag"))
    print(f"wrote {covered}/{total} answers to {out}")
    if wanted is not None:
        print("Incremental fill. Re-run the harness with --strict-evidence: it "
              "exits 3 while any served question is still unanswered, so repeat "
              "until it exits 0.")
        return 0
    if covered < total:
        print("INCOMPLETE -- re-run to resume before using this map for evidence.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
