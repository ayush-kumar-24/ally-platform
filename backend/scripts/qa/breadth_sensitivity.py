"""Weight sensitivity analysis for the evidence-breadth ranking factor.

Not a test. A test asserts a property; this reports what a weight DOES, across
every persona at once, so the weight is chosen from evidence rather than from
whichever number made one founder come out right.

The three fixtures are the QA personas reduced to the shape that matters, and
they pull in opposite directions on purpose:

  Siddharth  six dimensions vs one isolated Red -- breadth SHOULD win
  Desi       six answers in ONE dimension       -- breadth should NOT win
  Arya       four dimensions converging         -- breadth should win, mildly
  Severity   one Red in a high-risk category    -- severity MUST still win

A weight that fixes Siddharth by promoting Desi has not fixed anything.

Run: PYTHONPATH=. python scripts/qa/breadth_sensitivity.py
"""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

from app.api.v1.reasoning.config import RankingWeights
from app.api.v1.reasoning.engines.confidence import (
    WeightedConfidenceModel,
    evidence_breadth_value,
)
from app.api.v1.reasoning.engines.root_cause import StandardRootCauseEngine
from app.api.v1.reasoning.schemas import AnswerClassification, CategoryRisk
from app.models.enums import ConfirmationStatus, ScoreLabel

D = Decimal
GREEN, AMBER, RED = D("0"), D("1"), D("2")

#: The weights in scoring_rules today.
BASE = {"category_risk": D("0.40"), "confirmation_status": D("0.25"),
        "stage_probability": D("0.20"), "industry_probability": D("0.15")}

#: Candidate breadth weights. The budget is taken from industry_probability,
#: which contributed a neutral zero in all three live QA runs and is therefore
#: the cheapest donor. 0.20 exceeds industry's entire 0.15 budget, so it cannot
#: be funded this way at all -- reported rather than silently rescaled, because
#: "this weight is unaffordable without touching a factor that is doing work" is
#: the finding.
CANDIDATES = [D("0.00"), D("0.05"), D("0.10"), D("0.15"), D("0.20")]


def q(qid, rcid, category):
    return SimpleNamespace(question_id=qid, root_cause_id=rcid, category=category,
                           is_distress_tagged=False, follow_up_question_id=None)


def ans(aid, qid, score):
    label = (ScoreLabel.GREEN if score == GREEN
             else ScoreLabel.AMBER if score == AMBER else ScoreLabel.RED)
    return AnswerClassification(answer_id=aid, question_id=qid, label=label,
                                score=score, is_distress_flagged=False)


def ctx(weights: RankingWeights, multipliers=None):
    branching = SimpleNamespace(root_cause_min_detection_confidence=D("0"),
                                root_cause_max_candidates=0,
                                amber_cluster_trigger=3,
                                top_root_causes_report=3)
    return SimpleNamespace(
        stage_id=4,
        industry_id=None,
        config=SimpleNamespace(
            branching=branching,
            ranking_weights=weights,
            confirmation_multipliers=multipliers or SimpleNamespace(
                confirmed=D("1.5"), unconfirmed=D("1.0"), not_tested=D("0.5")),
            industry_probability=None,
        ),
    )


def weights_for(breadth: Decimal) -> RankingWeights:
    """Breadth funded from industry_probability, so the sum stays at 1.0."""
    industry = BASE["industry_probability"] - breadth
    return RankingWeights(
        category_risk=BASE["category_risk"],
        confirmation_status=BASE["confirmation_status"],
        stage_probability=BASE["stage_probability"],
        industry_probability=industry,
        evidence_breadth=breadth,
    )


# --- fixtures ---------------------------------------------------------------

SCENARIOS: dict[str, dict] = {
    "Siddharth: 6 dimensions vs 1 isolated Red": {
        "questions": [q(101, 1, "Sales & Revenue")] + [
            q(200 + i, 2, c) for i, c in enumerate(
                ["Target Customer & ICP", "Go-To-Market", "Product",
                 "Business Model Design", "Competitive Awareness",
                 "Business Planning"], start=1)
        ],
        "answers": [ans(1, 101, RED)] + [
            ans(10 + i, 200 + i, AMBER) for i in range(1, 7)],
        "risks": [CategoryRisk(category="Sales & Revenue", raw_score=D("1"),
                               max_score=D("1"), normalised_risk=D("0.60"),
                               is_flagged=True),
                  CategoryRisk(category="Target Customer & ICP", raw_score=D("1"),
                               max_score=D("1"), normalised_risk=D("0.60"),
                               is_flagged=True)],
        "labels": {1: "weak discovery (isolated)", 2: "unclear ICP (converging)"},
        "want": 2,
    },
    "Desi: 6 answers, ONE dimension": {
        "questions": [q(300 + i, 3, "Idea & Validation") for i in range(6)] + [
            q(401, 4, "Financial Management")],
        "answers": [ans(20 + i, 300 + i, AMBER) for i in range(6)] + [
            ans(40, 401, RED)],
        "risks": [CategoryRisk(category="Idea & Validation", raw_score=D("1"),
                               max_score=D("1"), normalised_risk=D("0.60"),
                               is_flagged=True),
                  CategoryRisk(category="Financial Management", raw_score=D("1"),
                               max_score=D("1"), normalised_risk=D("0.60"),
                               is_flagged=True)],
        "labels": {3: "friends+family (repeated, 1 dim)", 4: "pricing (isolated Red)"},
        "want": None,  # no required winner; watched for an undesirable flip
    },
    "Arya: 4 converging dimensions": {
        "questions": [q(500 + i, 5, c) for i, c in enumerate(
            ["Founder Psychology", "Operations & Systems", "Team & Leadership",
             "Business Planning"], start=1)] + [q(601, 6, "Marketing Execution")],
        "answers": [ans(50 + i, 500 + i, AMBER) for i in range(1, 5)] + [
            ans(60, 601, AMBER)],
        "risks": [CategoryRisk(category=c, raw_score=D("1"), max_score=D("1"),
                               normalised_risk=D("0.60"), is_flagged=True)
                  for c in ("Founder Psychology", "Marketing Execution")],
        "labels": {5: "founder dependency (4 dims)", 6: "marketing (1 dim)"},
        "want": 5,
    },
    "Severity guard: 1 Red, HIGH risk vs 4 dims, LOW risk": {
        "questions": [q(701, 7, "Financial Management")] + [
            q(800 + i, 8, c) for i, c in enumerate(
                ["Product", "Go-To-Market", "Team & Leadership",
                 "Business Planning"], start=1)],
        "answers": [ans(70, 701, RED)] + [
            ans(80 + i, 800 + i, AMBER) for i in range(1, 5)],
        "risks": [CategoryRisk(category="Financial Management", raw_score=D("1"),
                               max_score=D("1"), normalised_risk=D("1.00"),
                               is_flagged=True),
                  CategoryRisk(category="Product", raw_score=D("1"),
                               max_score=D("1"), normalised_risk=D("0.20"),
                               is_flagged=False)],
        "labels": {7: "severe, narrow (risk 1.00)", 8: "broad, mild (risk 0.20)"},
        "want": 7,  # severity must survive every candidate weight
    },
}


class _NoPriors:
    """Stage and industry priors absent, so the analysis isolates the factor
    under test. Absence is a supported state -- the model records it as
    unavailable and contributes neutral zero -- not a fixture cheat."""

    def get_stage_weights(self, _stage_id):
        return {}

    def get_industry_weights(self, *_a, **_k):
        return None


def category_risks_for(questions, answers):
    """Compute risks the way production does -- for EVERY answered category.

    Hand-written partial risk lists are what produced the earlier false finding
    that category_risk_score could be None in production. It cannot: every
    answered category gets a row. Mirroring that here keeps the analysis honest.
    """
    by_cat: dict[str, list] = {}
    cat_of = {x.question_id: x.category for x in questions}
    for a in answers:
        by_cat.setdefault(cat_of[a.question_id], []).append(a)
    rows = []
    for category, members in sorted(by_cat.items()):
        raw = sum((m.score for m in members), D("0"))
        max_score = D("2") * len(members)
        norm = min(D("1"), raw / max_score) if max_score else D("0")
        rows.append(CategoryRisk(category=category, raw_score=raw,
                                 max_score=max_score, normalised_risk=norm,
                                 is_flagged=norm >= D("0.5")))
    return rows


def run(scenario: dict, breadth: Decimal):
    w = weights_for(breadth)
    c = ctx(w)
    engine = StandardRootCauseEngine(repository=None)
    qmap = {x.question_id: x for x in scenario["questions"]}
    risks = category_risks_for(scenario["questions"], scenario["answers"])
    detections = engine.detect(list(scenario["answers"]), risks, qmap, c)
    model = WeightedConfidenceModel(repository=_NoPriors())
    scored = model.score_and_rank(detections, c)
    by_id = {d.root_cause_id: d for d in detections}
    return [(s.rank, s.root_cause_id, s.final_weighted_score,
             by_id[s.root_cause_id]) for s in scored]


def main() -> None:
    for title, scenario in SCENARIOS.items():
        print("=" * 78)
        print(title)
        print("=" * 78)
        baseline_winner = None
        for breadth in CANDIDATES:
            if breadth > BASE["industry_probability"]:
                print(f"  breadth={breadth}  UNAFFORDABLE from industry_probability "
                      f"({BASE['industry_probability']}) -- needs a proportional "
                      "rescale of factors that are doing work")
                continue
            rows = run(scenario, breadth)
            winner = rows[0][1]
            if breadth == D("0.00"):
                baseline_winner = winner
            flip = "" if winner == baseline_winner else "  <-- RANKING CHANGED"
            print(f"  breadth={breadth}  industry={BASE['industry_probability']-breadth}{flip}")
            for rank, rcid, score, det in rows:
                label = scenario["labels"].get(rcid, str(rcid))
                bv = evidence_breadth_value(det)
                direct = sum(1 for e in det.evidence if e.directness == "direct")
                print(f"     #{rank}  {label:<34} score={score}  "
                      f"dims={det.independent_signal_count} mass={det.evidence_mass} "
                      f"breadth={bv} direct={direct}/{len(det.evidence)} "
                      f"cat_founder={det.category_risk_score} "
                      f"cat_ranking={det.ranking_category_risk}")
            want = scenario.get("want")
            if want is not None:
                ok = "OK " if winner == want else "NOT MET"
                print(f"     required winner {scenario['labels'][want]!r}: {ok}")
            print()


if __name__ == "__main__":
    main()
