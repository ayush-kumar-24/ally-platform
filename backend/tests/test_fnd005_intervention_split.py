"""FND-005's action plans must match the audience their questions were written for.

THE DEFECT THIS LOCKS DOWN. The Stage 0->1 FND-005 questions (Q281-Q286) were
deliberately de-investorised -- Q281 asks what you would say to "someone smart
but unfamiliar with it", no investor anywhere in it. The interventions were not.
All three carried `stage_relevance = [2, 3, 4]`, which is exactly the Stage 0->1
cohort, and told those founders to "Cut your deck down", "Add your three
strongest traction metrics to the front of your deck" and "Ask an experienced
investor or advisor what they would want to see in the first three slides".
`capability_domain` is the founder-facing NAME of a recommendation
(service.py::intervention_labels), so a beauty-parlour franchisee with no
investor was being handed one headed "Investor-Centered Framing".

The scoping was inverted: investor text served ONLY to the stages whose
questions avoid investors, and withheld from stages 5-8 whose FND-005 questions
(Q143, Q157, Q1783...) are explicitly about decks and investors -- those
founders got no FND-005 recommendation at all.

The twelve FND-005 root causes split cleanly and every intervention straddled
the line. The fix is that split, not a rewording: cohort A gets INT-499, cohort
B keeps INT-366/367/368 rescoped to the stages they were written for.

Read off the COMMITTED reference SQL rather than a database, same as
test_dump_reference_data -- this is about what ships, and it must fail in CI on
a machine with no Postgres.
"""

import json
import re
from pathlib import Path

import pytest

REFERENCE = (Path(__file__).resolve().parents[1]
             / "data" / "reference" / "16_interventions.sql")

#: Root causes whose questions were rewritten for a general audience. Every one
#: has a Stage 0->1 question in the Q281-Q286 battery.
COHORT_A = {"RC-311", "RC-312", "RC-314", "RC-315", "RC-316", "RC-320"}

#: Root causes that are genuinely about investors and pitch materials. Every one
#: has ONLY Stage 1->10+ questions, and their definitions do not survive
#: de-investorising: RC-322 is "the founder does not understand how investors
#: evaluate opportunities", RC-318 is presentation quality.
COHORT_B = {"RC-313", "RC-317", "RC-318", "RC-319", "RC-321", "RC-322"}

STAGE_0_TO_1 = [2, 3, 4]      # Validation, Prototype/MVP, Early Traction
STAGE_1_TO_10 = [5, 6, 7, 8]  # Growth through Exit

#: Words that mean a step assumes a raise, an investor or pitch materials.
#: A LIST OF TERMS, not a gate -- nothing in the engine reads this. It exists so
#: that editing INT-499's prose back towards a deck fails a test instead of
#: reaching a founder.
INVESTOR_VOCABULARY = (
    "investor", "investors", "fundrais", "raise", "raising", "deck", "slide",
    "slides", "advisor", "advisers", "advisor's", "traction metric",
    "cap table", "term sheet", "valuation", "runway", "vc",
)


def _values(line: str) -> list[str | None]:
    """Split one `insert ... values (...)` row into its literals.

    A hand-rolled scan because the values contain jsonb: commas and parentheses
    inside a quoted literal are data, and `''` is an escaped quote. csv and
    str.split both get this wrong.
    """
    body = line[line.index(" values (") + len(" values ("):line.rindex(") on conflict")]
    out: list[str | None] = []
    i = 0
    while i < len(body):
        if body[i] == "'":
            i += 1
            buf = []
            while i < len(body):
                if body[i] == "'":
                    if i + 1 < len(body) and body[i + 1] == "'":
                        buf.append("'")
                        i += 2
                        continue
                    i += 1
                    break
                buf.append(body[i])
                i += 1
            out.append("".join(buf))
        elif body.startswith("NULL", i):
            out.append(None)
            i += 4
        elif body[i] in ", ":
            i += 1
        else:                                     # pragma: no cover - defensive
            raise AssertionError(f"unparsed literal at {i}: {body[i:i + 40]!r}")
    return out


def _rows() -> dict[str, dict]:
    """{intervention_code: {column: value}} for the whole committed table."""
    text = REFERENCE.read_text(encoding="utf-8")
    header = next(ln for ln in text.splitlines()
                  if ln.startswith('insert into "interventions"'))
    columns = re.findall(r'"([a-z_]+)"',
                         header[:header.index(" values (")])[1:]  # drop table name
    rows = {}
    for line in text.splitlines():
        if not line.startswith('insert into "interventions"'):
            continue
        row = dict(zip(columns, _values(line)))
        rows[row["intervention_code"]] = row
    return rows


@pytest.fixture(scope="module")
def rows():
    return _rows()


def _json(row, column):
    raw = row[column]
    return json.loads(raw) if raw else []


# --- A. INT-499 exists, with exactly the approved metadata -------------------

def test_int_499_exists(rows):
    assert "INT-499" in rows


def test_int_499_carries_the_approved_metadata(rows):
    r = rows["INT-499"]
    assert r["intervention_id"] == "499"
    assert r["problem_id"] == "30"                       # FND-005
    assert r["capability_domain"] == "Explaining the Business"
    assert r["section"] == "Fundraising"                 # mirrors problems.category
    assert _json(r, "stage_relevance") == STAGE_0_TO_1
    assert _json(r, "industry_relevance") == ["all"]
    assert _json(r, "design_principles") == [
        "minimum_effective_dose", "evidence_based"]
    assert _json(r, "secondary_root_cause_ids") == ["RC-314"]


def test_int_499_is_named_for_the_founder_not_the_catalogue(rows):
    """`capability_domain` is what the founder reads as the recommendation's
    name (reporting/generator.py::_label). It must not mention investors."""
    domain = rows["INT-499"]["capability_domain"].lower()
    assert not any(word in domain for word in INVESTOR_VOCABULARY)


# --- B. INT-499 serves exactly the six de-investorised root causes -----------

def test_int_499_serves_exactly_cohort_a(rows):
    assert set(_json(rows["INT-499"], "root_cause_ids")) == COHORT_A


def test_int_499_serves_no_investor_root_cause(rows):
    assert not set(_json(rows["INT-499"], "root_cause_ids")) & COHORT_B


def test_int_499_has_four_steps_one_per_construct(rows):
    """Four, not three: six root causes do not fit three steps without a step
    doing work for a construct it never names."""
    assert len(_json(rows["INT-499"], "immediate_next_steps")) == 4


@pytest.mark.parametrize("word", INVESTOR_VOCABULARY)
def test_no_int_499_step_assumes_an_investor_or_a_deck(rows, word):
    """Parametrised so a regression says WHICH word came back."""
    for step in _json(rows["INT-499"], "immediate_next_steps"):
        assert word not in step.lower(), f"{word!r} in: {step}"


def test_int_499_steps_work_without_customers_or_revenue(rows):
    """The evidence step is the one that could have excluded a pre-revenue
    founder. It must let "I have nothing" be a real answer -- the engine's
    "I don't know is not a weakness" property depends on it."""
    steps = _json(rows["INT-499"], "immediate_next_steps")
    evidence = next(s for s in steps if "claims" in s.lower())
    assert "Mark the ones where you have nothing" in evidence


def test_int_499_frameworks_are_real_and_not_the_investor_one(rows):
    r = rows["INT-499"]
    assert _json(r, "framework_codes") == ["FW-014", "FW-001"]
    names = {f["name"] for f in _json(r, "recommended_frameworks")}
    assert names == {"Obviously Awesome Positioning Framework", "The Mom Test"}
    assert "FW-047" not in _json(r, "framework_codes")   # Sequoia; INT-367's
    for framework in _json(r, "recommended_frameworks"):
        assert framework["brief"].strip()


# --- C. the three existing rows shed cohort A and are rescoped ---------------

@pytest.mark.parametrize("code,expected", [
    ("INT-366", {"RC-319", "RC-318", "RC-313"}),
    ("INT-367", {"RC-322", "RC-321"}),
    ("INT-368", {"RC-317"}),
])
def test_the_investor_interventions_serve_only_cohort_b(rows, code, expected):
    assert set(_json(rows[code], "root_cause_ids")) == expected


@pytest.mark.parametrize("code", ["INT-366", "INT-367", "INT-368"])
def test_no_investor_intervention_still_claims_a_de_investorised_cause(rows, code):
    """The regression that produced the live failure. If any of these reclaims a
    cohort-A root cause, a non-raising Stage 0->1 founder can be told to cut
    their deck down again."""
    served = set(_json(rows[code], "root_cause_ids"))
    served |= set(_json(rows[code], "secondary_root_cause_ids"))
    assert not served & COHORT_A


@pytest.mark.parametrize("code", ["INT-366", "INT-367", "INT-368"])
def test_the_investor_interventions_now_reach_the_stages_they_were_written_for(
        rows, code):
    """They were [2, 3, 4] -- the de-investorised cohort -- and so never reached
    the Growth-and-later founders whose FND-005 questions actually are about
    decks. DefaultInterventionRelevance matches stage_relevance against
    founder.stage_id, and stage_id == stage_order for all eight rows."""
    assert _json(rows[code], "stage_relevance") == STAGE_1_TO_10


def test_int_368_keeps_its_three_steps(rows):
    """Explicitly retained. The problem-statement and differentiation steps are
    still sound advice for an overloaded deck, and deleting them because their
    root-cause mapping moved would lose useful guidance for no gain."""
    steps = _json(rows["INT-368"], "immediate_next_steps")
    assert len(steps) == 3
    assert any("problem statement" in s.lower() for s in steps)
    assert any("different from the next closest competitor" in s.lower()
               for s in steps)


def test_int_368_secondary_causes_are_empty(rows):
    """RC-320 was secondary here and moved to INT-499; nothing replaced it."""
    assert _json(rows["INT-368"], "secondary_root_cause_ids") == []


@pytest.mark.parametrize("code,secondary", [
    ("INT-366", ["RC-313"]),
    ("INT-367", ["RC-321"]),
])
def test_untouched_secondary_causes_survive(rows, code, secondary):
    assert _json(rows[code], "secondary_root_cause_ids") == secondary


def test_int_367_keeps_the_investor_framework_where_it_belongs(rows):
    """FW-047 (Sequoia) is correct for RC-321/RC-322 and wrong everywhere else.
    It stays; it just no longer reaches founders who are not raising."""
    names = {f["name"] for f in _json(rows["INT-367"], "recommended_frameworks")}
    assert "Sequoia Capital Story Framework" in names


# --- D. the split is complete and disjoint ----------------------------------

def test_every_fnd_005_root_cause_is_served_exactly_once(rows):
    """The check that makes the split safe to ship. Missing a cause leaves a
    founder with a finding and no action; serving one twice sends two
    recommendations for one problem."""
    served = []
    for code in ("INT-366", "INT-367", "INT-368", "INT-499"):
        served += _json(rows[code], "root_cause_ids")
    assert len(served) == len(set(served)), "a root cause is served twice"
    assert set(served) == COHORT_A | COHORT_B


def test_the_two_cohorts_do_not_overlap(rows):
    assert not COHORT_A & COHORT_B
    assert len(COHORT_A | COHORT_B) == 12


def test_stage_coverage_has_no_hole(rows):
    """Somebody at every stage from Validation on can receive an FND-005 action
    plan. Rescoping the three without adding INT-499 would have left Stage 0->1
    with a finding and nothing to do about it."""
    covered = set()
    for code in ("INT-366", "INT-367", "INT-368", "INT-499"):
        covered |= set(_json(rows[code], "stage_relevance"))
    assert covered == set(STAGE_0_TO_1) | set(STAGE_1_TO_10)
