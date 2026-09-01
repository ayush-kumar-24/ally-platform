"""What does the diagnosis actually ask a HEALTHY founder?

Drives the real `QuestionSelectionEngine` against a snapshot of the live Stage 0
question bank, with an in-memory repository standing in for Postgres. No
selection policy is reimplemented here -- the engine does all the ranking
exactly as it does in production; the stub only answers the four calls the
engine makes of its repository.

The simulated founder is healthy: every answer scores green, so no root causes
are detected and the session never enters validate mode. That is the point.
Every real session on record was driven by a deliberately struggling persona,
so nothing told us what a founder in good shape is asked, or for how long.

Run:
    DATABASE_URL=postgresql+psycopg://u:p@127.0.0.1:5432/none \
    SECRET_KEY=calibration \
    python backend/scripts/calibration/selection_calibration.py

Neither env var is connected to -- they only satisfy Settings at import.

The JSON snapshots alongside this file were taken from the live database. Refresh
them when the bank changes; the queries that produced them are in the module
docstring of `refresh_snapshot.sql`.
"""
import json
import os
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parents[1]))
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://u:p@127.0.0.1:5432/none")
os.environ.setdefault("SECRET_KEY", "calibration-only-not-a-real-secret")

from app.api.v1.diagnosis.engine import QuestionSelectionEngine  # noqa: E402

BANK = json.loads((HERE / "bank_stage0.json").read_text())
PILLARS = {p: pid for p, pid in json.loads((HERE / "pillar_map.json").read_text())}
CATEGORIES = BANK["categories"]
PILLAR_NAMES = {
    1: "Founder Readiness", 2: "Market Clarity", 3: "Revenue Maturity",
    4: "Product & Execution", 5: "Team & Leadership", 6: "Strategic Clarity",
}

#: Pillars an ideation-stage founder should be asked about. Founder Readiness is
#: the Founder DNA layer; Market Clarity carries Idea & Validation, Target
#: Customer & ICP and Competitive Awareness. The other four are Business DNA and
#: have no meaning before there is a product, revenue or a team.
STAGE_0_IN_SCOPE = {"Founder Readiness", "Market Clarity"}


class Q:
    """Stands in for a `questions` row -- only the fields the engine reads."""
    __slots__ = ("question_id", "category", "priority", "difficulty_level",
                 "problem_id", "root_cause_id")

    def __init__(self, qid, cat_idx, pri, diff, problem_id):
        self.question_id = qid
        self.category = CATEGORIES[cat_idx]
        self.priority = "CORE" if pri == 0 else "SUPPLEMENTARY"
        self.difficulty_level = diff
        self.problem_id = problem_id
        self.root_cause_id = None


class Session:
    def __init__(self, routing_state="continue"):
        self.session_id = 9001
        self.routing_state = routing_state


class Stage:
    def __init__(self, stage_order):
        self.stage_order = stage_order


class Founder:
    def __init__(self, stage_order):
        self.founder_id = 9001
        self.stage = Stage(stage_order)
        self.stage_id = stage_order


class StubRepo:
    """The four calls the engine makes, served from the snapshot in memory."""

    def __init__(self, questions):
        self.all = questions
        self.answered = set()
        self.per_pillar_category = Counter()

    def list_candidate_questions(self, session_id, stage_groups, founder_id):
        return [q for q in self.all if q.question_id not in self.answered]

    def problem_to_pillar(self):
        return PILLARS

    def answered_count_per_pillar_category(self, session_id):
        return dict(self.per_pillar_category)

    def get_detected_root_cause_ids(self, session_id):
        return set()

    def record(self, q):
        self.answered.add(q.question_id)
        pillar = PILLARS.get(q.problem_id)
        if pillar is not None:
            self.per_pillar_category[(pillar, q.category)] += 1


def run(budget=30):
    questions = [Q(*row) for row in BANK["rows"]]
    repo = StubRepo(questions)
    engine = QuestionSelectionEngine(repo)
    session, founder = Session(), Founder(stage_order=1)

    asked = []
    for _ in range(budget):
        q = engine.select_next_question(session, founder)
        if q is None:
            break
        asked.append(q)
        repo.record(q)

    print("=" * 78)
    print(f"HEALTHY STAGE 0 (IDEATION) FOUNDER -- budget {budget}")
    print("=" * 78)
    print(f"asked {len(asked)} of {len(questions)} eligible Stage 0 questions\n")

    print("ASK ORDER")
    for i, q in enumerate(asked, 1):
        pillar = PILLAR_NAMES.get(PILLARS.get(q.problem_id), "UNMAPPED")
        scope = "  " if pillar in STAGE_0_IN_SCOPE else "!!"
        new = "NEW" if q.question_id >= 2130 else "   "
        print(f"  {scope} {i:2}. id={q.question_id:<5} {new}  "
              f"{pillar:<20} {q.category:<26} {q.priority}")

    by_pillar = Counter(PILLAR_NAMES.get(PILLARS.get(q.problem_id), "UNMAPPED")
                        for q in asked)
    print("\nPILLAR COVERAGE")
    for name in list(PILLAR_NAMES.values()) + ["UNMAPPED"]:
        n = by_pillar.get(name, 0)
        note = "" if name in STAGE_0_IN_SCOPE or not n else "  <-- Business DNA at ideation"
        if n:
            print(f"  {name:<20} {n:>3}  {'#' * n}{note}")

    out_of_scope = [q for q in asked
                    if PILLAR_NAMES.get(PILLARS.get(q.problem_id)) not in STAGE_0_IN_SCOPE]
    print(f"\nSTAGE 0 SCOPE: {len(asked) - len(out_of_scope)} of {len(asked)} in scope, "
          f"{len(out_of_scope)} out of scope "
          f"({len(out_of_scope) / len(asked) * 100:.0f}%)")

    revenue_team = [q for q in out_of_scope
                    if PILLAR_NAMES.get(PILLARS.get(q.problem_id))
                    in {"Revenue Maturity", "Team & Leadership"}]
    print(f"  of those, {len(revenue_team)} ask a pre-launch solo founder about "
          f"revenue models or team structure")

    new_n = sum(1 for q in asked if q.question_id >= 2130)
    eligible_new = sum(1 for q in questions if q.question_id >= 2130)
    print(f"\nNEW BANK (ids >= 2130): {new_n} of {len(asked)} asked "
          f"({new_n / len(asked) * 100:.0f}%); {eligible_new} of {len(questions)} eligible")
    return asked


if __name__ == "__main__":
    run()
