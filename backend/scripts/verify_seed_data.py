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
        "founder_stages": (8, 8), "industries": (4, 4), "readiness_pillars": (6, 6),
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
        "select coalesce(sum(rule_value),0) from scoring_rules where rule_code in "
        "('WEIGHT_CATEGORY_RISK','WEIGHT_CONFIRMATION_STATUS','WEIGHT_STAGE_PROBABILITY','WEIGHT_INDUSTRY_PROBABILITY')"
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
