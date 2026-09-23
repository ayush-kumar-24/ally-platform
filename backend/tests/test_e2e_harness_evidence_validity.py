"""The two guards that decide whether an e2e run may be read as evidence.

Both were defects found while validating the diagnosis engine, and both had the
same shape: `valid_for_diagnostic_evidence` asserted something the run did not
support, so a batch of worthless runs read as results.

  D1  `degraded` was set only inside an `elif failed:` branch, reachable only
      when at least one provider call was made. A run where NOTHING reached a
      model -- dead key, exhausted account, or scoring simply off -- printed a
      warning and was stamped valid.

  D2  a coverage gap was reported only on the `--answer-map` path. Persona mode,
      the default, filled every question it had no answer for with one invented
      string and reported clean.

Hermetic: these exercise the two pure helpers, so no database, no network and
no model. Importing the harness module is safe -- it is data and functions.
"""

import pytest

from scripts.e2e_journey_check import (
    MAX_FILLER_SHARE,
    coverage_gap_reason,
    evidence_degraded_reason,
)


def _valid(degraded, gap):
    """The stamp the script writes: exactly `not (degraded or coverage_gap)`."""
    return not (degraded or gap)


# --------------------------------------------------------------------------
# D1 -- provider calls
# --------------------------------------------------------------------------

def test_d1_zero_calls_is_invalid():
    """THE regression. Zero calls used to return None and stamp the run valid."""
    reason = evidence_degraded_reason(calls_observable=True, made=0, failed=0)
    assert reason is not None
    assert "ZERO" in reason
    assert not _valid(reason, None)


def test_d1_zero_calls_invalid_even_with_zero_failures():
    """`failed == 0` must not read as health when nothing was attempted.

    This is the exact shape of the bug: the old code reached `elif failed:`,
    found 0, and fell through to None.
    """
    assert evidence_degraded_reason(calls_observable=True, made=0, failed=0)


def test_d1_unobservable_call_log_is_invalid():
    """A run we could not watch does not support a positive validity claim."""
    reason = evidence_degraded_reason(calls_observable=False, made=0, failed=0)
    assert reason is not None
    assert "llm_call_log" in reason


def test_d1_partial_failures_still_degraded():
    """Pre-existing behaviour must survive the fix."""
    reason = evidence_degraded_reason(calls_observable=True, made=30, failed=7)
    assert reason is not None
    assert "7 of 30" in reason


def test_d1_successful_calls_are_not_degraded():
    assert evidence_degraded_reason(calls_observable=True, made=30, failed=0) is None


# --------------------------------------------------------------------------
# D2 -- answer coverage
# --------------------------------------------------------------------------

def test_d2_persona_filler_above_ceiling_is_a_gap():
    """The observed desi_bar run: 11 of 46 served answers were filler (24%)."""
    reason = coverage_gap_reason(harness_misses=0, filler=11, served=46)
    assert reason is not None
    assert "11 of 46" in reason and "24%" in reason
    assert not _valid(None, reason)


def test_d2_persona_filler_below_ceiling_is_not_a_gap():
    assert coverage_gap_reason(harness_misses=0, filler=4, served=46) is None


def test_d2_ceiling_is_exclusive_at_the_boundary():
    """Exactly at the ceiling passes; one more answer over it does not."""
    assert coverage_gap_reason(harness_misses=0, filler=20, served=100) is None
    assert coverage_gap_reason(harness_misses=0, filler=21, served=100) is not None


def test_d2_ceiling_is_configurable():
    """--max-filler-share moves the line, and the message says where it is."""
    assert coverage_gap_reason(harness_misses=0, filler=11, served=46,
                               max_filler_share=0.5) is None
    strict = coverage_gap_reason(harness_misses=0, filler=1, served=46,
                                 max_filler_share=0.0)
    assert strict is not None and "0%" in strict


def test_d2_no_filler_is_never_a_gap():
    assert coverage_gap_reason(harness_misses=0, filler=0, served=46) is None


def test_d2_unmeasured_coverage_is_a_gap():
    """--repeat-answers keeps no ledger, so the filler share is unknown."""
    reason = coverage_gap_reason(harness_misses=0, filler=None, served=None)
    assert reason is not None
    assert "not measured" in reason


def test_d2_harness_miss_still_reported():
    """Pre-existing --answer-map behaviour must survive the fix."""
    reason = coverage_gap_reason(harness_misses=3, filler=None, served=None)
    assert reason is not None
    assert "3 questions had no prepared answer" in reason


# --------------------------------------------------------------------------
# The three cases the fix was commissioned to prove
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "name, made, failed, filler, served, expect_valid",
    [
        ("0 model calls",                    0,  0, 2,  46, False),
        ("insufficient genuine answers",    31,  0, 11, 46, False),
        ("adequate answers + real calls",   31,  0, 2,  46, True),
    ],
)
def test_commissioned_cases(name, made, failed, filler, served, expect_valid):
    degraded = evidence_degraded_reason(calls_observable=True, made=made,
                                        failed=failed)
    gap = coverage_gap_reason(harness_misses=0, filler=filler, served=served)
    assert _valid(degraded, gap) is expect_valid, (name, degraded, gap)


def test_default_ceiling_is_one_in_five():
    assert MAX_FILLER_SHARE == pytest.approx(0.20)
