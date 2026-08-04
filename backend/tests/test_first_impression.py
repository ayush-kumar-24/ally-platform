"""The founder's first impression: derivation, parsing, and degradation.

The point of these is the failure paths. The happy path (a working model) is the
easy case; what matters is that a founder reaching the "Reading between the
lines" screen always gets something true, whatever the provider is doing.
"""

import asyncio
import types

from app.api.v1.impression import service
from app.api.v1.impression.derive import derive_impression
from app.api.v1.impression.facts import facts_from_founder
from app.api.v1.impression.service import _clip, _parse, get_or_create


class _Stage:
    def __init__(self, name, label):
        self.stage_name = name
        self.onboarding_label = label


def _founder(**overrides):
    """A founder row stub carrying the shapes onboarding actually stores."""
    base = dict(
        founder_id=1,
        full_name="Rahul Menon",
        stage=_Stage("Growth / Scaling", "Stage 1→10+"),
        building_summary="Scheduling software for small clinics.",
        problem_statement="Clinics lose bookings to double-booked slots.",
        founder_motivation="My mother ran a clinic on paper diaries.",
        customer_segment=["Doctors", "Businesses"],
        customer_segment_other="",
        industry="Healthcare",
        current_challenges=["Hiring", "Cash flow", "Scaling"],
        goal_90_day="Get 40 clinics onto paid plans.",
        vision_1_year="Three hundred clinics across Maharashtra.",
        support_preferences=["Strategic thinking", "Hiring"],
        experience_level="one_company",
        emotional_state=["determined"],
        adaptive_reflection="We win clinics faster than we onboard them.",
        first_impression=None,
        first_impression_at=None,
    )
    base.update(overrides)
    return types.SimpleNamespace(**base)


class _Db:
    """Just enough Session for _persist."""
    def __init__(self):
        self.committed = False
    def add(self, _obj):
        pass
    def commit(self):
        self.committed = True
    def rollback(self):
        pass


# --- facts ------------------------------------------------------------------

def test_facts_turn_enums_back_into_labels():
    f = facts_from_founder(_founder())
    assert f.experience == "Built one company"     # not 'one_company'
    assert f.feeling == "Determined"               # not 'determined'
    assert f.first_name == "Rahul"
    assert f.stage_group == "Stage 1→10+"


def test_facts_survive_a_bare_founder():
    """Every onboarding field is nullable; reading them must not explode."""
    bare = _founder(
        stage=None, building_summary=None, problem_statement=None,
        founder_motivation=None, customer_segment=None, current_challenges=None,
        experience_level=None, emotional_state=None, full_name=None,
    )
    f = facts_from_founder(bare)
    assert f.complete_enough is False
    assert f.challenges == [] and f.audience == []


# --- derived read -----------------------------------------------------------

def test_derived_read_uses_the_founders_own_answers():
    f = facts_from_founder(_founder())
    out = derive_impression(f)
    assert out.source == "derived"
    assert 1 <= len(out.bullets) <= 4
    blob = " ".join(out.bullets) + out.read
    assert "Growth / Scaling" in blob
    # It should say something about the pressure they named, not just echo it.
    assert out.instinct.startswith("Your instinct when")


def test_derived_read_differs_by_founder():
    """A rule-based read still has to be about *this* founder -- two different
    founders must not get the same words."""
    a = derive_impression(facts_from_founder(_founder()))
    b = derive_impression(facts_from_founder(_founder(
        stage=_Stage("Ideation", "Stage 0"),
        current_challenges=["Getting customers"],
        experience_level="first_time",
        emotional_state=["overwhelmed"],
    )))
    assert a.read != b.read
    assert a.instinct != b.instinct


def test_derived_read_acknowledges_strain():
    strained = derive_impression(facts_from_founder(
        _founder(emotional_state=["overwhelmed"]),
    ))
    assert "overwhelmed" in strained.read.lower()


# --- parsing the model reply ------------------------------------------------

def _reply(**over):
    body = {
        "bullets": ["Noted one", "Heard two", "Flagged three", "Read four"],
        "read": "A short read.",
        "instinct": "Your instinct when tired is to keep going.",
    }
    body.update(over)
    import json
    return json.dumps(body)


def test_parse_accepts_a_fenced_reply():
    assert _parse("```json\n" + _reply() + "\n```") is not None


def test_parse_accepts_prose_around_the_object():
    assert _parse("Here you go:\n" + _reply() + "\nHope that helps.") is not None


def test_parse_rejects_incomplete_replies():
    assert _parse("") is None
    assert _parse("not json at all") is None
    assert _parse(_reply(bullets=[])) is None        # no bullets
    assert _parse(_reply(read="")) is None           # no read
    assert _parse(_reply(instinct="")) is None       # nothing to confirm


def test_clip_never_cuts_mid_word():
    long = "Placed stop checking the bank balance next to cash flow as a challenge the pressure is personal not just operational"
    out = _clip(long, 110)
    assert out.endswith("…")
    assert not out.rstrip("…").endswith("operationa")   # the bug this fixes
    assert out.rstrip("…").split(" ")[-1] in long.split(" ")


# --- the service: degradation is the contract -------------------------------

def test_model_failure_falls_back_to_the_derived_read(monkeypatch):
    monkeypatch.setattr(
        service, "_generate_with_model",
        lambda db, founder, facts: asyncio.sleep(0, result=None),
    )
    env = asyncio.run(get_or_create(_Db(), _founder()))
    assert env.available is True
    assert env.impression.source == "derived"       # not an error, not empty


def test_stored_impression_is_served_without_regenerating(monkeypatch):
    def _boom(*_a, **_k):
        raise AssertionError("must not call the model when one is stored")
    monkeypatch.setattr(service, "_generate_with_model", _boom)

    founder = _founder(first_impression={
        "bullets": ["Kept one"], "read": "Kept read.",
        "instinct": "Your instinct when kept is kept.", "source": "llm",
    })
    env = asyncio.run(get_or_create(_Db(), founder))
    assert env.impression.read == "Kept read."
    assert env.impression.source == "llm"


def test_incomplete_onboarding_reports_unavailable(monkeypatch):
    monkeypatch.setattr(
        service, "_generate_with_model",
        lambda db, founder, facts: asyncio.sleep(0, result=None),
    )
    env = asyncio.run(get_or_create(_Db(), _founder(
        stage=None, building_summary=None, problem_statement=None,
        founder_motivation=None,
    )))
    assert env.available is False
    assert env.impression is None


def test_a_broken_stored_shape_is_regenerated(monkeypatch):
    monkeypatch.setattr(
        service, "_generate_with_model",
        lambda db, founder, facts: asyncio.sleep(0, result=None),
    )
    # Missing 'instinct' -- an older shape we no longer serve.
    founder = _founder(first_impression={"bullets": ["x"], "read": "y"})
    env = asyncio.run(get_or_create(_Db(), founder))
    assert env.available is True
    assert env.impression.instinct                  # regenerated, not blank


def test_persist_failure_still_serves_the_founder(monkeypatch):
    monkeypatch.setattr(
        service, "_generate_with_model",
        lambda db, founder, facts: asyncio.sleep(0, result=None),
    )

    class _FailingDb(_Db):
        def commit(self):
            raise RuntimeError("database is down")

    env = asyncio.run(get_or_create(_FailingDb(), _founder()))
    assert env.available is True
    assert env.impression.read                      # storing failed; screen did not
