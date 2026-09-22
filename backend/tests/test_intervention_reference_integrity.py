"""Interventions must reference root-cause CODES, never root-cause IDS.

`interventions.root_cause_ids` stores codes (`RC-001`), matched by exact string
join against `root_causes.root_cause_code`. The two numbering schemes coincide
for ids 1-999 -- id 1 is `RC-001` -- and then diverge: id 1815 is `RC-1813`.

So a reference written from an id is silently wrong in one of two ways. Below
1000 it dangles (`RC-1` matches nothing) and the intervention is simply never
offered. Above it, the id happens to BE a valid code, so it resolves -- to the
wrong root cause, sometimes one belonging to a different problem entirely. That
second form raises no error anywhere: the founder is handed an action plan for a
cause they were not diagnosed with.

The defect was found in two waves, and the second is why the tests below check
whole LISTS and not just individual references:

  * 132 references over 30 interventions dangled (ids below 1444, where no such
    code exists). Visible: the intervention was simply never offered.
  * 518 references over a further 53 interventions RESOLVED -- to the wrong
    cause. 210 of those crossed into a neighbouring problem and were findable
    that way; the other 308 landed on the wrong cause INSIDE the right problem
    and were invisible to any per-reference check. For all 53 the entire primary
    list was the id-set of the intervention's own problem, so a reference-level
    test could never have found them.

Together they disabled 99 of the 163 root causes that had no intervention at all
and mis-attached 518 more. These tests hold the corrected file to the rule and
would fail again on a bad re-dump.

Hermetic: parses `data/reference/*.sql`, no database.
"""

import json
import re
from pathlib import Path

import pytest

REFERENCE = Path(__file__).resolve().parents[1] / "data" / "reference"
ROOT_CAUSES = REFERENCE / "14_root_causes.sql"
INTERVENTIONS = REFERENCE / "16_interventions.sql"

#: A json array holding only RC codes -- the two reference columns and nothing
#: else. At least ONE entry is required: an empty `[]` is matched by several
#: other columns (`framework_codes` among them), and treating one as a reference
#: column silently shifts every position after it.
_RC_ARRAY = re.compile(r"'(\[\"RC-[^\"]*\"(?:, \"RC-[^\"]*\")*\])'")
_INT_CODE = re.compile(r"'(INT-[^']+)'")
_RC_CODE = re.compile(r"'(RC-[A-Za-z0-9-]+)'")


def _inserts(path):
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            if line.startswith("insert into"):
                yield line


def _root_causes():
    """{code: problem_id} and {id: code}, straight from the dump."""
    by_code, by_id = {}, {}
    for line in _inserts(ROOT_CAUSES):
        rc_id = int(re.search(r"values \('(\d+)',", line).group(1))
        code = _RC_CODE.search(line).group(1)
        problem = re.search(r"'(\d+)', '[^']*', '" + re.escape(code) + r"'", line)
        by_id[rc_id] = code
        if problem:
            by_code[code] = int(problem.group(1))
    return by_code, by_id


def _interventions():
    """[(intervention_code, problem_id, [primary...], [secondary...])]"""
    out = []
    for line in _inserts(INTERVENTIONS):
        code = _INT_CODE.search(line).group(1)
        problem = int(re.search(r"'" + re.escape(code) + r"', '(\d+)'", line).group(1))
        arrays = [json.loads(a) for a in _RC_ARRAY.findall(line)]
        primary = arrays[0] if arrays else []
        secondary = arrays[1] if len(arrays) > 1 else []
        out.append((code, problem, primary, secondary))
    return out


BY_CODE, BY_ID = _root_causes()
INTERVENTION_ROWS = _interventions()

#: problem_id -> the ids of its root causes, and -> their codes. The two sets
#: are what separates a list written from ids from one written from codes.
PROBLEM_IDS: dict[int, set[int]] = {}
PROBLEM_CODES: dict[int, set[str]] = {}
for _code, _problem in BY_CODE.items():
    PROBLEM_CODES.setdefault(_problem, set()).add(_code)
for _rc_id, _code in BY_ID.items():
    if _code in BY_CODE:
        PROBLEM_IDS.setdefault(BY_CODE[_code], set()).add(_rc_id)

#: The interventions the id-as-code defect had broken. Pinned by name so a
#: regression names the row rather than just moving a count.
CORRECTED = {
    "INT-245", "INT-276", "INT-277", "INT-278", "INT-279", "INT-280", "INT-281",
    "INT-282", "INT-283", "INT-284", "INT-285", "INT-286", "INT-287", "INT-288",
    "INT-289", "INT-290", "INT-291", "INT-292", "INT-293", "INT-294", "INT-295",
    "INT-296", "INT-297", "INT-298", "INT-299", "INT-300", "INT-301", "INT-302",
    "INT-303", "INT-304",
}


# --- the dumps parse at all -------------------------------------------------

def test_both_reference_dumps_parse():
    assert len(BY_ID) == 2009, "root-cause dump did not parse as expected"
    assert len(INTERVENTION_ROWS) == 417, "intervention dump did not parse as expected"


# --- the rule ---------------------------------------------------------------

def test_every_intervention_reference_resolves_to_a_known_root_cause():
    """Zero orphans. A reference matching nothing is an intervention that can
    never be offered for that cause, and nothing in the engine reports it."""
    orphans = [
        (code, ref)
        for code, _problem, primary, secondary in INTERVENTION_ROWS
        for ref in primary + secondary
        if ref not in BY_CODE
    ]
    assert orphans == []


def test_no_reference_is_a_root_cause_id_wearing_a_code_s_clothes():
    """The defect itself, stated directly: `RC-<n>` where <n> is a root-cause ID
    whose real code is something else."""
    wrong = []
    for code, _problem, primary, secondary in INTERVENTION_ROWS:
        for ref in primary + secondary:
            m = re.fullmatch(r"RC-(\d+)", ref)
            if not m:
                continue
            as_id = int(m.group(1))
            real = BY_ID.get(as_id)
            if real is not None and real != ref and ref not in BY_CODE:
                wrong.append((code, ref, real))
    assert wrong == []


def test_no_short_form_reference_survives():
    """`RC-1` for `RC-001` -- the form the whole 99 took. Codes are zero-padded
    to at least three digits."""
    short = [
        (code, ref)
        for code, _problem, primary, secondary in INTERVENTION_ROWS
        for ref in primary + secondary
        if re.fullmatch(r"RC-\d{1,2}", ref)
    ]
    assert short == []


def test_no_intervention_references_the_same_cause_twice():
    """Correcting an id to its code can collide with an entry already present;
    a duplicate would double that cause's weight in the recommendation pass."""
    dupes = [
        (code, kind)
        for code, _problem, primary, secondary in INTERVENTION_ROWS
        for kind, arr in (("primary", primary), ("secondary", secondary))
        if len(arr) != len(set(arr))
    ]
    assert dupes == []


# --- the corrected rows specifically ----------------------------------------

@pytest.mark.parametrize("intervention", sorted(CORRECTED))
def test_each_corrected_intervention_has_no_orphan_references(intervention):
    rows = {c: (p, s) for c, _pid, p, s in INTERVENTION_ROWS}
    assert intervention in rows, f"{intervention} vanished from the dump"
    primary, secondary = rows[intervention]
    assert primary, f"{intervention} lost its primary references"
    assert [r for r in primary + secondary if r not in BY_CODE] == []


@pytest.mark.parametrize("intervention", sorted(CORRECTED))
def test_each_corrected_intervention_stays_inside_its_own_problem(intervention):
    """The check that separates a repair from a guess: every corrected reference
    lands on a root cause of the intervention's OWN problem. That is why the
    id-to-code mapping is the right reading and not merely a plausible one."""
    row = next(r for r in INTERVENTION_ROWS if r[0] == intervention)
    _code, problem, primary, _secondary = row
    strays = [(ref, BY_CODE.get(ref)) for ref in primary if BY_CODE.get(ref) != problem]
    assert strays == []


# --- the systematic form: whole lists written from ids ----------------------

def test_no_intervention_list_is_its_problem_s_ID_set():
    """The check that would have caught all 518 on day one.

    Per-reference tests cannot see this. A list written from ids resolves
    happily -- every entry is a real code -- and 308 of the 518 stayed inside
    the right problem, so even the problem check missed them. What gives it away
    is the SHAPE: the numbers in the list are exactly the root-cause IDS of the
    intervention's own problem, while the codes of that problem are different
    numbers entirely.
    """
    id_written = []
    for code, problem, primary, _secondary in INTERVENTION_ROWS:
        if not primary:
            continue
        numbers = {int(r[3:]) for r in primary if re.fullmatch(r"RC-\d+", r)}
        if not numbers:
            continue
        # Sound, and deliberately incomplete. A list written from CODES is
        # flagged only if its numbers fall inside the problem's id-set AND it
        # is not already a valid code set for that problem -- the second
        # clause is load-bearing, because for the 1,631 causes whose offset is
        # 0 a correct code IS 'RC-<its own id>' and every one of them would
        # otherwise be flagged.
        #
        # Where a problem's id range and code range OVERLAP, no shape test can
        # decide: problem 210 spans ids 1556-1562 and codes RC-1554-RC-1560, so
        # a correct list and an id-written one are indistinguishable by shape
        # alone. INT-494 and INT-496 live there and are pinned by value below
        # instead of being guessed at here.
        looks_like_ids = numbers <= PROBLEM_IDS.get(problem, set())
        are_codes = set(primary) <= PROBLEM_CODES.get(problem, set())
        if looks_like_ids and not are_codes:
            id_written.append((code, problem, sorted(primary)))
    assert id_written == []


def test_every_reference_belongs_to_its_intervention_s_own_problem():
    """After both corrections, no reference crosses a problem boundary.

    One exception is carried deliberately: INT-MKT-032 is seeded by an Alembic
    migration rather than this dump, its `RC-MKT-057` is non-numeric so the
    id-to-code rule cannot apply to it, and choosing a replacement is a content
    judgement nobody has made. It is not in this file, so it cannot be asserted
    on here -- named so the next reader knows it is outstanding, not missed.
    """
    strays = [
        (code, ref, BY_CODE.get(ref), problem)
        for code, problem, primary, secondary in INTERVENTION_ROWS
        for ref in primary + secondary
        if BY_CODE.get(ref) != problem
    ]
    assert strays == []


def test_the_correction_is_a_lookup_and_not_arithmetic():
    """Guards the rule itself, not just its result.

    `root_cause_id - code_number` is 0 for 1,631 causes and 2 for 378 of them
    (ids 1444-1821). Every one of the 518 lived in that second block, which is
    exactly why a "-2" rule looks right and is wrong: applied anywhere else it
    would corrupt correct references. If this ever becomes a single offset, the
    shortcut becomes tempting -- so fail here and say why.
    """
    offsets = {rc_id - int(code[3:])
               for rc_id, code in BY_ID.items() if re.fullmatch(r"RC-\d+", code)}
    assert offsets == {0, 2}, (
        "the id/code offset changed; the correction must stay a lookup by "
        "root_cause_id, never arithmetic on the code number"
    )


# --- INT-245: a restoration, not a lookup -----------------------------------

#: INT-245 is the one intervention the 132-reference correction damaged. Its
#: original list was all seven of problem 247's causes written as ids 1815-1821.
#: Two of those dangled; correcting them collided with entries already present
#: and de-duplication dropped them, taking it from 10 references to 7. Applying
#: the id-to-code lookup to what survived would have produced `RC-1816` in the
#: secondary list -- a cause the author never selected -- so it was restored
#: from the pre-image instead. These values are pinned because nothing else in
#: the file records that history.
INT_245_PRIMARY = [
    "RC-1813", "RC-1814", "RC-1815", "RC-1816", "RC-1817", "RC-1818", "RC-1819",
]
INT_245_SECONDARY = ["RC-1817", "RC-1818", "RC-1819"]


def _int_245():
    return next(r for r in INTERVENTION_ROWS if r[0] == "INT-245")


def test_int_245_primary_is_the_restored_authored_set():
    _code, _problem, primary, _secondary = _int_245()
    assert primary == INT_245_PRIMARY


def test_int_245_secondary_is_the_restored_authored_set():
    """The sharp one. The lookup applied to the damaged list yields RC-1816,
    which appears nowhere in the authored set."""
    _code, _problem, _primary, secondary = _int_245()
    assert secondary == INT_245_SECONDARY
    assert "RC-1816" not in secondary


def test_int_245_covers_every_root_cause_of_its_problem():
    """Problem 247 has exactly seven causes and the intervention addresses all
    of them -- which is what the de-duplication had silently undone."""
    _code, problem, primary, _secondary = _int_245()
    assert set(primary) == PROBLEM_CODES[problem]


# --- INT-MKT-032 is outside the deterministic rule, by construction ---------

def test_int_mkt_032_is_not_governed_by_this_file():
    """Named so it is visibly outstanding rather than quietly missed.

    `INT-MKT-032` references `RC-MKT-057`, which belongs to problem 534 while
    the intervention belongs to 532. It is NOT the id-as-code defect and the
    lookup cannot reach it: `RC-MKT-057` carries no integer to read as a
    root_cause_id, and the MKT code series has no offset relation to ids
    (`RC-MKT-056` is id 3190, `RC-MKT-057` is id 3191, but the code numbers are
    56 and 57). Choosing a replacement is a content decision nobody has made.

    It is also seeded by an Alembic migration rather than this dump, so it
    cannot be corrected here at all -- which this test asserts, so that if it
    ever DOES arrive in the dump, the cross-problem test above starts failing
    and someone has to decide.
    """
    assert "INT-MKT-032" not in {row[0] for row in INTERVENTION_ROWS}


def test_the_deterministic_rule_only_applies_to_numeric_codes():
    """Why INT-MKT-032 is excluded, stated as a property rather than a name:
    the lookup needs an integer, and non-numeric codes have none."""
    # Every code in THIS dump is numeric, so the rule is total over it. The
    # non-numeric series (RC-MKT-*, RC-AGR-*, ...) are seeded by migrations and
    # are precisely the ones the rule cannot reach -- INT-MKT-032 among them.
    non_numeric = [c for c in BY_CODE if not re.fullmatch(r"RC-\d+", c)]
    assert non_numeric == [], (
        "a non-numeric root-cause code has entered this dump; the id-to-code "
        "lookup cannot resolve one, so the reference tests above no longer "
        "cover every row"
    )


# --- the cases shape cannot reach, pinned by value --------------------------

#: Where a problem's id range overlaps its code range, a correct reference list
#: and one written from ids look identical. These four were all corrected by
#: lookup (INT-493/494/495/496) and are pinned so a regression is caught by
#: value rather than by a heuristic that cannot see it.
PINNED = {
    "INT-493": (["RC-1554", "RC-1555", "RC-1557", "RC-1558"], ["RC-1558"]),
    "INT-494": (["RC-1556", "RC-1559", "RC-1560"], ["RC-1560"]),
    "INT-495": (["RC-1695", "RC-1694", "RC-1696", "RC-1698"], ["RC-1698"]),
    "INT-496": (["RC-1699", "RC-1697", "RC-1700"], ["RC-1700"]),
}


@pytest.mark.parametrize("intervention", sorted(PINNED))
def test_overlap_region_interventions_keep_their_corrected_references(intervention):
    row = next(r for r in INTERVENTION_ROWS if r[0] == intervention)
    _code, problem, primary, secondary = row
    want_primary, want_secondary = PINNED[intervention]
    assert primary == want_primary
    assert secondary == want_secondary
    # and they are still genuinely inside their own problem
    for ref in primary + secondary:
        assert BY_CODE[ref] == problem
