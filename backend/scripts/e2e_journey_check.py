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

TWO WAYS TO GET A FOUNDER, because `founders.user_id` may or may not carry a
foreign key to `auth.users`:

  --stage N          Creates a synthetic founder with a random user_id. Works
                      on a database with NO such FK -- a disposable local
                      Postgres provisioned by `alembic upgrade heads` alone,
                      since that FK is not created by any migration in this
                      repo (verified: no alembic version references
                      auth.users or founders_user_id_fkey for the founders
                      table itself). It fails, correctly, against a database
                      where that FK exists.

  --founder-email E   Looks up an EXISTING founder by email instead of
  --founder-id N      creating one -- required for a real Supabase project,
                      where `founders.user_id` genuinely references
                      `auth.users` (added outside this repo's migration
                      history, presumably via the Supabase dashboard). This
                      script will not, and should not, fabricate a row in
                      Supabase's own managed auth schema: it can't see the
                      password-hash format, confirmation tokens, or GoTrue
                      triggers that schema depends on, and a raw INSERT that
                      merely satisfies the FK's type is not the same thing as
                      a real identity. Use an account you already control --
                      ideally your own, signed up through the app the normal
                      way -- not a stranger's real data. --founder-id is the
                      same lookup keyed on the primary key instead of email,
                      for when you already know the id and would rather not
                      pass an email on the command line at all.

    python -m scripts.e2e_journey_check --database-url "postgresql+psycopg2://..." --stage 1 --confirm-writes
    python -m scripts.e2e_journey_check --database-url "..." --founder-email you@example.com --confirm-writes
    python -m scripts.e2e_journey_check --database-url "..." --founder-id 12345 --confirm-writes
    python -m scripts.e2e_journey_check --database-url "..." --cleanup
    python -m scripts.e2e_journey_check --database-url "..." --cleanup-founder-email you@example.com
    python -m scripts.e2e_journey_check --database-url "..." --cleanup-founder-id 12345

IT WRITES. In --stage mode: a founder, consent, a Founder DNA run, a Current
Problem run, a diagnosis session and its answers, and a report. Every founder
it creates is named `e2e+<timestamp>@ally-e2e.local`; `--cleanup` deletes every
founder at that domain and everything cascading from them.

In --founder-email / --founder-id mode it never creates or deletes a
`founders` or `founder_consents` row -- it writes only a Founder DNA run, a
Current Problem run, a diagnosis session and its answers, and a report, all
against the founder_id that account already owns.
`--cleanup-founder-email` / `--cleanup-founder-id` remove exactly those
(sessions, answers, DNA answers, current-problem answers, reports) and leave
the founder and their consent in place -- that account is real and outlives
this script.

The one exception, and it matters: cleanup also sets
`founders.founder_dna_completed_at` and `current_problem_completed_at` back
to null. Those two columns are journey state living on the founder row, not
identity. Cleanup used to skip them to keep a "writes nothing to founders"
promise, and the result was a founder with the answers deleted but still
flagged as having finished: founder-dna/start and current-problem/start then
returned no question at all, both phases walked zero questions, and the run
still printed a full-looking report built on the diagnosis alone.

The database URL must be passed explicitly -- it deliberately does NOT read
DATABASE_URL, so pointing this at a real project has to be a decision rather
than an accident. `--confirm-writes` is required on top of that.

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


#: Rows a test run of either mode can add, in the order they must be deleted
#: (children before parents). `founders` and `founder_consents` are NOT here
#: -- --stage mode deletes them separately for its own synthetic founders,
#: --founder-email mode never touches them at all.
_JOURNEY_TABLES = (
    ("answers", "founder_id"), ("founder_dna_answers", "founder_id"),
    ("current_problem_answers", "founder_id"), ("founder_reports", "founder_id"),
    ("detected_root_causes", "session_id"), ("sessions", "founder_id"),
)


#: Journey state that lives on the `founders` row itself rather than in a
#: child table. Deleting the answers without clearing these leaves a founder
#: marked complete with nothing behind it -- and the next run's
#: founder-dna/start and current-problem/start then serve no question at all,
#: because `current_state()` short-circuits on the timestamp. That is how a
#: journey check came back "0 question(s) answered" for two whole phases.
_JOURNEY_STAMPS = ("founder_dna_completed_at", "current_problem_completed_at")


def _clear_journey_stamps(db, sa, founder_ids: list) -> None:
    """Reset the phase-completion timestamps on `founders`.

    This is the one place cleanup touches the founders row, and it is
    deliberate: these two columns are journey state, not identity. Nothing
    about who the founder is, their consent, plan or profile is altered --
    only the record of having finished a phase, which is exactly what
    cleanup is removing everywhere else.
    """
    try:
        db.execute(sa.text(
            "update founders set "
            + ", ".join(f"{c} = null" for c in _JOURNEY_STAMPS)
            + " where founder_id = any(:f)"), {"f": founder_ids})
    except Exception:                                            # noqa: BLE001
        db.rollback()  # column may not exist on this schema; keep going


def _delete_journey_rows(db, sa, founder_ids: list) -> None:
    _clear_journey_stamps(db, sa, founder_ids)
    for table, col in _JOURNEY_TABLES:
        try:
            if col == "session_id":
                db.execute(sa.text(
                    f"delete from {table} where session_id in "
                    "(select session_id from sessions where founder_id = any(:f))"),
                    {"f": founder_ids})
            else:
                db.execute(sa.text(f"delete from {table} where {col} = any(:f)"),
                           {"f": founder_ids})
        except Exception:                                        # noqa: BLE001
            db.rollback()  # table may not exist on this schema; keep going


def cleanup(db, sa) -> int:
    """Removes every synthetic --stage founder (@ally-e2e.local) entirely."""
    founders = [r[0] for r in db.execute(sa.text(
        "select founder_id from founders where email like :p"),
        {"p": f"%@{TEST_DOMAIN}"}).all()]
    if not founders:
        print(f"  nothing to clean up at @{TEST_DOMAIN}")
        return 0
    _delete_journey_rows(db, sa, founders)
    try:
        db.execute(sa.text("delete from founder_consents where founder_id = any(:f)"),
                   {"f": founders})
    except Exception:                                            # noqa: BLE001
        db.rollback()
    db.execute(sa.text("delete from founders where founder_id = any(:f)"), {"f": founders})
    db.commit()
    print(f"  removed {len(founders)} test founder(s) and their data")
    return len(founders)


def cleanup_founder_journey(db, sa, *, fid: int | None = None, email: str | None = None,
                           label: str | None = None) -> int:
    """Removes journey rows for one EXISTING, real founder.

    Never removes the founder or their consent -- that account is real and
    outlives this script. It does write two columns ON the founders row:
    founder_dna_completed_at and current_problem_completed_at are reset to
    null, because they record having finished a phase whose answers this
    function is deleting. Leaving them set is what made a cleaned founder
    unable to re-run Founder DNA or Current Problem at all.
    """
    if fid is None:
        fid = db.execute(sa.text("select founder_id from founders where email = :e"),
                         {"e": email}).scalar()
        if fid is None:
            print(f"  no founder found with email {email}")
            return 0
    label = label or f"founder_id={fid}"
    _delete_journey_rows(db, sa, [fid])
    db.commit()
    print(f"  removed journey data for {label} "
          "(the founder and their consent were left alone)")
    return 1


def _seed_founder(db, sa, stage_order: int) -> tuple[int, str]:
    """A brand-new synthetic founder with a random user_id.

    Only works where founders.user_id carries no FK to auth.users -- see the
    module docstring. Raises IntegrityError with a clear message, rather than
    a bare traceback, when that FK exists and rejects the fabricated id.
    """
    email = f"e2e+{int(time.time())}@{TEST_DOMAIN}"
    try:
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
    except Exception as exc:                                      # noqa: BLE001
        db.rollback()
        if "user_id" in str(exc) and ("fkey" in str(exc).lower() or "foreign key" in str(exc).lower()):
            raise SystemExit(
                "\n  This database enforces a real foreign key from "
                "founders.user_id to auth.users -- a random UUID cannot "
                "satisfy it, by design (see the module docstring).\n"
                "  Use --founder-email <email> instead, naming an account "
                "that already exists (ideally your own, signed up through "
                "the app normally)."
            ) from exc
        raise
    db.execute(sa.text("""
        insert into founder_consents (consent_id, founder_id, terms_version,
                                      privacy_version, agree_terms, agree_diagnosis)
        values (gen_random_uuid(), :f, 'v1', 'v1', true, true)"""), {"f": fid})
    db.commit()
    return fid, email


def _resolve_existing_founder(db, sa, *, email: str | None = None,
                              founder_id: int | None = None) -> tuple[int, str]:
    """An EXISTING founder's id, by email or by id -- exactly one of the two.

    Never inserts into founders or founder_consents -- see the module
    docstring for why. Returns (fid, label): label is the email when looked up
    by email, or `founder_id=N` when looked up by id, so id-mode never has to
    read or print an email it was not given.
    """
    assert (email is None) != (founder_id is None), "pass exactly one of email/founder_id"

    if email is not None:
        row = db.execute(sa.text(
            "select founder_id, stage_id, profile_completed from founders "
            "where email = :e"), {"e": email}).first()
        not_found = (
            f"\n  No founder exists with email {email!r} on this database.\n"
            "  --founder-email requires an account that already exists -- "
            "sign up through the app first, or use --stage on a database "
            "with no auth.users FK instead."
        )
        label = email
    else:
        row = db.execute(sa.text(
            "select founder_id, stage_id, profile_completed from founders "
            "where founder_id = :f"), {"f": founder_id}).first()
        not_found = (
            f"\n  No founder exists with founder_id={founder_id} on this database.\n"
            "  --founder-id requires an account that already exists -- "
            "sign up through the app first, or use --stage on a database "
            "with no auth.users FK instead."
        )
        label = f"founder_id={founder_id}"

    if row is None:
        raise SystemExit(not_found)
    fid, stage_id, profile_completed = row
    if not profile_completed:
        print(f"  warning: {label} has profile_completed=false; onboarding "
              "gates may reject the journey below.")
    has_consent = db.execute(sa.text(
        "select 1 from founder_consents where founder_id = :f limit 1"),
        {"f": fid}).first()
    if has_consent is None:
        raise SystemExit(
            f"\n  {label} has no consent record, and this script will not "
            "create one on a real account -- consent must come from the "
            "founder themselves, through the app.\n"
            "  Complete consent in the app for this account, then re-run."
        )
    return fid, label


def _walk(client, start_path, answer_path, id_field, label, out):
    """Drive one question/answer phase to completion, recording every question."""
    r = client.post(start_path)
    if r.status_code not in (200, 201):
        print(f"  FAIL {start_path} -> {r.status_code} {r.text[:200]}")
        return False
    q = (r.json() or {}).get("question")
    if q is None:
        # A null question means "this phase is already complete for this
        # founder" -- and that is a FAILURE here, not a pass. This check
        # exists to prove the phases run; a phase that served nothing proved
        # nothing. It used to slip through: `while q:` simply never entered,
        # and the walk printed "0 question(s) answered" and returned True
        # under a confident-looking summary.
        #
        # The usual cause is exactly the one this script can create: cleanup
        # removes the answer rows but the completion timestamp on `founders`
        # (founder_dna_completed_at / current_problem_completed_at) stays set,
        # leaving the founder marked complete with no answers behind it.
        print(f"  FAIL {label}: no question served -- this phase reports "
              "itself already complete for this founder.\n"
              "       Run --cleanup-founder-id <id> (which now clears the "
              "completion timestamps too) and try again.")
        return False
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
    if not out:
        print(f"  FAIL {label}: 0 questions answered")
        return False
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
    if args.cleanup_founder_email or args.cleanup_founder_id:
        print("CLEANUP (single founder)")
        with SessionLocal() as db:
            if args.cleanup_founder_email:
                cleanup_founder_journey(db, sa, email=args.cleanup_founder_email)
            else:
                cleanup_founder_journey(db, sa, fid=args.cleanup_founder_id)
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

    using_existing = bool(args.founder_email or args.founder_id)
    with SessionLocal() as db:
        calls_before, cost_before = _llm_calls(db, sa)
        if using_existing:
            fid, label = _resolve_existing_founder(
                db, sa, email=args.founder_email, founder_id=args.founder_id)
            print(f"\n  existing founder {fid} ({label}) (unchanged: not created "
                  "by this script)")
        else:
            fid, label = _seed_founder(db, sa, args.stage)
            print(f"\n  test founder {fid} <{label}> at stage_order {args.stage}")

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

    if args.founder_email:
        print(f"\n  clean up with: --database-url ... --cleanup-founder-email {label}")
    elif args.founder_id:
        print(f"\n  clean up with: --database-url ... --cleanup-founder-id {fid}")
    else:
        print(f"\n  clean up with: --database-url ... --cleanup")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--database-url", required=True,
                   help="SQLAlchemy URL. Deliberately NOT read from DATABASE_URL -- "
                        "this script writes, so the target has to be named.")
    p.add_argument("--stage", type=int, default=1, choices=range(1, 9),
                   help="founder_stages.stage_order for a NEW synthetic founder "
                        "(default 1, Ideation). Ignored with --founder-email. "
                        "Only works on a database with no auth.users FK on "
                        "founders.user_id -- see the module docstring.")
    p.add_argument("--founder-email", metavar="EMAIL",
                   help="use an EXISTING founder by email instead of creating one "
                        "-- required against a real Supabase project. That "
                        "account must already exist, with profile and consent "
                        "completed through the app; this script never creates "
                        "either on your behalf.")
    p.add_argument("--founder-id", type=int, metavar="N",
                   help="same as --founder-email, but by founder_id -- avoids "
                        "naming an email on the command line at all")
    p.add_argument("--confirm-writes", action="store_true",
                   help="required: acknowledges that this writes a diagnosis "
                        "journey and a report into the named database")
    p.add_argument("--cleanup", action="store_true",
                   help=f"delete every @{TEST_DOMAIN} founder and their data, then exit")
    p.add_argument("--cleanup-founder-email", metavar="EMAIL",
                   help="delete the journey data (sessions/answers/report) for "
                        "one existing founder by email, then exit -- leaves the "
                        "founder and their consent untouched")
    p.add_argument("--cleanup-founder-id", type=int, metavar="N",
                   help="same as --cleanup-founder-email, but by founder_id")
    p.add_argument("--allow-unscored", action="store_true",
                   help="run even with scoring off (useful only to test the fallback)")
    p.add_argument("--json-out", metavar="FILE", help="write the full transcript as JSON")
    args = p.parse_args(argv)

    exit_actions = [args.cleanup, bool(args.cleanup_founder_email),
                    bool(args.cleanup_founder_id)]
    if sum(exit_actions) > 1:
        p.error("--cleanup / --cleanup-founder-email / --cleanup-founder-id "
                "are mutually exclusive")
    if not args.confirm_writes and not any(exit_actions):
        p.error("--confirm-writes is required (or one of the --cleanup* flags)")

    if args.founder_email and args.founder_id:
        p.error("--founder-email and --founder-id are mutually exclusive")
    if args.stage != 1 and (args.founder_email or args.founder_id):
        p.error("--stage is ignored with --founder-email/--founder-id -- drop one of them")
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
