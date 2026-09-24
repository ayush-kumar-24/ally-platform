"""Full seeded-data verification (staging).

There is no seed *script* in the repo -- the reference catalogue was seeded via
Supabase. This script is the counterpart: it verifies the seeded data is present,
internally consistent, and satisfies the business invariants the engines rely on.
Read-only. Exits non-zero if any HARD check fails, so it can gate a release.

    python scripts/verify_seed_data.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text

from app.db.session import SessionLocal

_OK, _FAIL = "  [PASS]", "  [FAIL]"


def main() -> int:
    db = SessionLocal()
    failures = 0

    def q(sql: str, **p):
        return db.execute(text(sql), p).scalar()

    def check(label: str, ok: bool, detail: str = "") -> None:
        nonlocal failures
        print(f"{_OK if ok else _FAIL} {label}" + (f" -- {detail}" if detail else ""))
        if not ok:
            failures += 1

    print("== Catalogue presence (counts) ==")
    counts = {
        "founder_stages": (8, 8), "industries": (30, 30), "readiness_pillars": (6, 6),
        "session_state_bands": (4, 4), "psychological_state_signals": (20, None),
        "chronic_state_inference": (1, None), "prompt_library": (1, None),
        "archetypes": (8, 8), "scoring_rules": (20, None), "problems": (1, None),
        "root_causes": (1, None), "interventions": (1, None),
        "root_cause_weights": (1, None), "questions": (1, None), "blind_spots": (1, None),
    }
    for tbl, (lo, hi) in counts.items():
        n = q(f"select count(*) from {tbl}")
        ok = n >= lo and (hi is None or n == hi)
        check(f"{tbl} = {n}", ok, "" if ok else f"expected >= {lo}" + (f" and == {hi}" if hi else ""))

    print("\n== Referential integrity (0 orphans expected) ==")
    orphans = {
        "questions.problem_id -> problems":
            "select count(*) from questions q where q.problem_id is not null and not exists (select 1 from problems p where p.problem_id=q.problem_id)",
        "questions.root_cause_id -> root_causes":
            "select count(*) from questions q where q.root_cause_id is not null and not exists (select 1 from root_causes r where r.root_cause_id=q.root_cause_id)",
        "root_causes.problem_id -> problems":
            "select count(*) from root_causes r where r.problem_id is not null and not exists (select 1 from problems p where p.problem_id=r.problem_id)",
        "interventions.problem_id -> problems":
            "select count(*) from interventions i where i.problem_id is not null and not exists (select 1 from problems p where p.problem_id=i.problem_id)",
        "problems.pillar_id -> readiness_pillars":
            "select count(*) from problems p where p.pillar_id is not null and not exists (select 1 from readiness_pillars rp where rp.pillar_id=p.pillar_id)",
        "root_cause_weights.root_cause_id -> root_causes":
            "select count(*) from root_cause_weights w where not exists (select 1 from root_causes r where r.root_cause_id=w.root_cause_id)",
        "root_cause_weights.stage_id -> founder_stages":
            "select count(*) from root_cause_weights w where not exists (select 1 from founder_stages s where s.stage_id=w.stage_id)",
    }
    for label, sql in orphans.items():
        n = q(sql)
        check(f"{label}", n == 0, "" if n == 0 else f"{n} orphan row(s)")

    print("\n== Business invariants ==")
    pillar_sum = q("select coalesce(sum(pillar_weightage),0) from readiness_pillars")
    check("readiness_pillars weightage sums to 100", float(pillar_sum) == 100.0, f"got {pillar_sum}")

    rank_sum = q(
        # WEIGHT_EVIDENCE_BREADTH belongs in this sum. Migration d3e8b41c9a52
        # moved 0.15 of the budget from WEIGHT_INDUSTRY_PROBABILITY (which can
        # never contribute -- root_cause_weights has no industry column) to
        # breadth, and updated check_scoring_weights_sum() to enumerate five
        # factors. This check kept summing the original four, so on a CORRECT
        # database it reported 0.85 and failed. A release gate that fails on a
        # correct database is worse than no gate: it trains people to ignore it.
        "select coalesce(sum(rule_value),0) from scoring_rules where rule_code in "
        "('WEIGHT_CATEGORY_RISK','WEIGHT_CONFIRMATION_STATUS','WEIGHT_STAGE_PROBABILITY',"
        "'WEIGHT_INDUSTRY_PROBABILITY','WEIGHT_EVIDENCE_BREADTH')"
    )
    check("root-cause ranking weights sum to 1.0", abs(float(rank_sum) - 1.0) < 1e-6, f"got {rank_sum}")

    conf_sum = q(
        "select coalesce(sum(rule_value),0) from scoring_rules where rule_code in "
        "('CONFIDENCE_WEIGHT_CATEGORY_SIGNAL','CONFIDENCE_WEIGHT_COVERAGE','CONFIDENCE_WEIGHT_CONSISTENCY',"
        "'CONFIDENCE_WEIGHT_CONFIRMATION','CONFIDENCE_WEIGHT_SEPARATION')"
    )
    check("confidence weights sum to 1.0", abs(float(conf_sum) - 1.0) < 1e-6, f"got {conf_sum}")

    # Validate against the canonical stage-group labels (avoids arrow-char pitfalls).
    bad_stage_group = q(
        "select count(*) from questions q where q.primary_stage_group is not null and "
        "q.primary_stage_group not in (select distinct onboarding_label from founder_stages where onboarding_label is not null)"
    )
    check("questions.primary_stage_group values are valid", bad_stage_group == 0, f"{bad_stage_group} invalid")

    # ------------------------------------------------------------------
    # The industry feature, which fails OPEN and therefore fails SILENTLY.
    #
    # Every one of these checks exists because a rebuild following
    # docs/RESTORE.md passed every check above it while the industry feature
    # was completely dead. Step 4 of that procedure reloads `industries` and
    # `questions` from data/reference/, and that snapshot predates the industry
    # work: 4 industries instead of 30, and no `industry_relevance` column at
    # all. The selection code then treated all 1,800 industry questions as
    # universal -- no error, no warning, and a SaaS founder was a valid
    # candidate for "out of 100 deliveries, how many arrive damaged?".
    #
    # Measured on that rebuild: a stage-6 SaaS founder was asked ZERO questions
    # written for her industry. The same founder on a correct database gets 14
    # of 32, the first 13 forced by the opening block.
    #
    # A gate that cannot see that is not gating the thing that matters.
    # ------------------------------------------------------------------
    print("\n== Industry-adaptive selection ==")

    industry_questions = q(
        "select count(*) from questions where industry_relevance is not null "
        "and industry_relevance <> '[\"all\"]'::jsonb"
    )
    check("questions carry an industry", industry_questions > 0,
          "" if industry_questions else
          "0 -- every question is universal, so the industry feature is OFF "
          "for every founder. Usual cause: questions reloaded from a dump "
          "taken before industry_relevance existed")

    mapping_rows = q("select count(*) from question_industry_mapping")
    check("question_industry_mapping is populated", mapping_rows > 0,
          f"{mapping_rows} rows" if mapping_rows else
          "0 -- the gate, the ranking and the opening block all read this table")

    orphan_mappings = q(
        "select count(*) from question_industry_mapping m where not exists "
        "(select 1 from industries i where i.industry_code = m.industry_code)"
    )
    check("every mapped industry_code resolves", orphan_mappings == 0,
          "" if orphan_mappings == 0 else
          f"{orphan_mappings} mapping row(s) name an industry that no longer "
          "exists -- industries was reloaded from a stale dump")

    # Not a hard failure: weights only sharpen ranking, and a missing set
    # degrades to the universal ordering rather than breaking anything.
    weighted = q(
        "select count(*) from industries where top_pain_point_weights is not null "
        "and top_pain_point_weights::text not in ('{}', 'null')"
    )
    total_industries = q("select count(*) from industries")
    print(f"  [INFO] industries with pain-point weights: "
          f"{weighted}/{total_industries}   (0 weakens ranking, never breaks it)")

    # ------------------------------------------------------------------
    # Can the diagnosis actually RECOMMEND anything?
    #
    # A founder's report ends in interventions, and they are looked up by the
    # problem behind each detected root cause. A root cause whose problem has
    # no intervention row contributes a finding and no action -- the report
    # generates, names three root causes, and hands over an empty
    # recommended_intervention_ids. Nothing errors.
    #
    # This is not hypothetical either. The first version of the skip list in
    # docs/RESTORE.md kept the migration-seeded interventions and dropped the
    # reference file, and the two sets turned out to be DISJOINT by problem:
    # the migrations cover problems 276-725 (the newer dimension layer) and the
    # reference file covers 1-269 (the original catalogue). A rebuild that kept
    # only one of them left HALF the root-cause catalogue -- 2,009 of 3,996 --
    # unable to produce a single recommendation, and the industry checks above
    # all passed while it did.
    #
    # Measured on the live database for calibration: 36 of 3,996 root causes
    # (0.9%) have no intervention, and 6 of 723 problems are uncovered. Some
    # genuine gaps are therefore expected and must not fail the build. Half the
    # catalogue is not a gap, it is a missing table, so the threshold sits well
    # clear of both numbers.
    # ------------------------------------------------------------------
    print("\n== Interventions reachable from root causes ==")

    rc_total = q("select count(*) from root_causes")
    rc_orphan = q(
        "select count(*) from root_causes r where not exists "
        "(select 1 from interventions i where i.problem_id = r.problem_id)"
    )
    share = (rc_orphan / rc_total) if rc_total else 0.0
    check(
        "root causes can reach an intervention",
        share <= 0.05,
        f"{rc_orphan}/{rc_total} ({share:.1%}) cannot -- a diagnosis landing on "
        "one of these produces a report with no recommendations. Usual cause: "
        "interventions loaded from only one of the two catalogues"
        if share > 0.05 else f"{rc_orphan}/{rc_total} ({share:.1%}) cannot",
    )

    uncovered_problems = q(
        "select count(*) from problems p "
        " where exists (select 1 from root_causes r where r.problem_id = p.problem_id) "
        "   and not exists (select 1 from interventions i where i.problem_id = p.problem_id)"
    )
    print(f"  [INFO] problems carrying root causes but no intervention: "
          f"{uncovered_problems}")

    print("\n== Embeddings (RAG / semantic) ==")
    for tbl in ("root_causes", "problems", "questions", "agent_interpretations", "rag_chunks"):
        total = q(f"select count(*) from {tbl}")
        emb = q(f"select count(embedding) from {tbl}")
        print(f"  {tbl}: {emb}/{total} embedded")

    db.close()
    print("\n" + ("=" * 48))
    if failures:
        print(f"RESULT: {failures} HARD CHECK(S) FAILED")
        return 1
    print("RESULT: all hard checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
