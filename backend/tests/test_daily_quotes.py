"""Choosing each founder's two lines: the narrowing, the parsing, the fallback.

The failure this whole feature exists to fix is "every founder reads the same
sentence", so the tests that matter most are the ones about SPREAD -- that two
founders at the same stage on the same day do not land on the same pair. A
selector that is merely deterministic passes a naive test and reintroduces the
bug.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.quotes.catalogue import BY_ID, QUOTES, STAGES, THEMES
from app.quotes.service import (
    SURFACES,
    FounderContext,
    _parse,
    _themes_from,
    fallback_pick,
    model_pick,
    shortlist,
)

TODAY = date(2026, 9, 17)


# --- the catalogue -----------------------------------------------------------

def test_no_line_is_attributed():
    """The product renders no author, so a line carrying one in its text -- an
    em-dash credit smuggled into the sentence -- would render as part of it."""
    for q in QUOTES:
        assert "—" not in q.text, f"{q.id} looks like it carries an attribution"


def test_every_stage_has_a_real_choice():
    for stage in STAGES:
        available = [q for q in QUOTES if not q.stages or stage in q.stages]
        assert len(available) >= 12, f"{stage} has only {len(available)}"


def test_ids_are_unique():
    assert len(BY_ID) == len(QUOTES)


# --- reading the founder's challenges ----------------------------------------

def test_themes_are_read_from_a_list():
    assert "money" in _themes_from(["runway is short", "pricing"])


def test_themes_are_read_from_a_dict_of_flags():
    """`current_challenges` is a schemaless jsonb and has held both shapes."""
    assert "team" in _themes_from({"hiring": True, "something_else": False})


def test_themes_survive_a_bare_string_and_none():
    assert "customers" in _themes_from("finding customers")
    assert _themes_from(None) == ()


def test_themes_come_back_in_catalogue_order():
    """Set iteration order would make the prompt and the shortlist differ run
    to run for no reason."""
    got = _themes_from(["hiring", "runway", "customers"])
    assert list(got) == [t for t in THEMES if t in got]


# --- the shortlist -----------------------------------------------------------

def test_a_stage_filters_out_other_stages_lines():
    ctx = FounderContext(founder_id=1, stage="ideation")
    for q in shortlist(ctx):
        assert not q.stages or "ideation" in q.stages


def test_no_stage_means_everything_is_eligible():
    """A founder who never finished onboarding still gets a full card."""
    ctx = FounderContext(founder_id=1)
    assert len(shortlist(ctx)) >= 12


def test_matching_themes_rank_first():
    ctx = FounderContext(founder_id=1, themes=("money",))
    top = shortlist(ctx)[:5]
    assert any("money" in q.themes for q in top)


def test_the_shortlist_is_not_only_the_matching_theme():
    """A slice of nothing but money lines would hand this founder the same two
    every fortnight."""
    ctx = FounderContext(founder_id=1, themes=("money",))
    picked = shortlist(ctx)
    assert any("money" not in q.themes for q in picked)


def test_recently_seen_lines_are_excluded():
    ctx = FounderContext(founder_id=1, stage="growth")
    first = shortlist(ctx)
    banned = frozenset(q.id for q in first[:3])
    again = shortlist(ctx, exclude=banned)
    assert banned.isdisjoint({q.id for q in again})


def test_excluding_everything_still_returns_a_card():
    """A founder who has read the whole catalogue gets repeats, not a blank."""
    ctx = FounderContext(founder_id=1)
    assert shortlist(ctx, exclude=frozenset(q.id for q in QUOTES))


# --- the deterministic fallback ----------------------------------------------

def test_fallback_gives_two_different_lines():
    ctx = FounderContext(founder_id=7)
    picks = fallback_pick(ctx, list(QUOTES), TODAY)
    assert set(picks) == set(SURFACES)
    assert picks["compass"] != picks["plan"]


def test_fallback_is_stable_for_the_day():
    """A refresh must not reshuffle the card."""
    ctx = FounderContext(founder_id=7)
    assert fallback_pick(ctx, list(QUOTES), TODAY) == fallback_pick(ctx, list(QUOTES), TODAY)


def test_fallback_moves_on_the_next_day():
    ctx = FounderContext(founder_id=7)
    assert fallback_pick(ctx, list(QUOTES), TODAY) != fallback_pick(ctx, list(QUOTES), date(2026, 9, 18))


def test_neighbouring_founders_do_not_read_the_same_pair():
    """THE bug this feature exists to fix, in its subtlest form: founder ids are
    sequential, so `founder_id % len` puts everyone who signed up the same
    afternoon on adjacent lines every single day."""
    seen = [tuple(fallback_pick(FounderContext(founder_id=i), list(QUOTES), TODAY).values())
            for i in range(1, 41)]
    assert len(set(seen)) >= 25, f"only {len(set(seen))} distinct pairs across 40 founders"


def test_fallback_survives_a_two_line_shortlist():
    ctx = FounderContext(founder_id=3)
    picks = fallback_pick(ctx, list(QUOTES)[:2], TODAY)
    assert picks["compass"] != picks["plan"]


def test_fallback_survives_an_empty_shortlist():
    picks = fallback_pick(FounderContext(founder_id=3), [], TODAY)
    assert picks["compass"] != picks["plan"]


# --- parsing what the model says ---------------------------------------------

ALLOWED = {"a", "b", "c"}


def test_a_clean_reply_is_accepted():
    assert _parse('{"compass": "a", "plan": "b"}', ALLOWED) == {"compass": "a", "plan": "b"}


def test_json_wrapped_in_prose_is_still_read():
    assert _parse('Sure!\n```json\n{"compass":"a","plan":"c"}\n```', ALLOWED)


def test_an_id_outside_the_shortlist_is_refused():
    """The shape a made-up line arrives in."""
    assert _parse('{"compass": "a", "plan": "invented"}', ALLOWED) is None


def test_the_same_line_on_both_pages_is_refused():
    assert _parse('{"compass": "a", "plan": "a"}', ALLOWED) is None


def test_a_missing_surface_is_refused():
    assert _parse('{"compass": "a"}', ALLOWED) is None


@pytest.mark.parametrize("reply", ["", "no json", "{bad}", "[1,2]", '"text"', '{"compass": 3, "plan": "b"}'])
def test_unusable_replies_are_refused(reply):
    assert _parse(reply, ALLOWED) is None


# --- the call ----------------------------------------------------------------

class _Boom:
    async def generate(self, request):
        raise RuntimeError("provider is down")


class _Reply:
    def __init__(self, text):
        self._text = text

    async def generate(self, request):
        class R:
            text = self._text
        return R()


def test_a_provider_failure_returns_none_rather_than_raising():
    """The nightly job falls back; the founder never learns which happened."""
    ctx = FounderContext(founder_id=1)
    assert model_pick(_Boom(), ctx, list(QUOTES)) is None


def test_a_good_reply_comes_back_parsed():
    ctx = FounderContext(founder_id=1)
    candidates = list(QUOTES)[:5]
    a, b = candidates[0].id, candidates[1].id
    provider = _Reply('{"compass": "%s", "plan": "%s"}' % (a, b))
    assert model_pick(provider, ctx, candidates) == {"compass": a, "plan": b}


def test_too_few_candidates_makes_no_call_at_all():
    assert model_pick(_Boom(), FounderContext(founder_id=1), list(QUOTES)[:1]) is None


# --- what the prompt is allowed to know --------------------------------------

def test_the_description_carries_situation_not_identity():
    ctx = FounderContext(founder_id=42, stage="growth", industry="healthtech",
                         themes=("money", "team"), flagged=True)
    described = ctx.describe()
    assert "growth" in described and "healthtech" in described and "money" in described
    # The founder's id is the key we hash on, never something the model sees.
    assert "42" not in described


def test_an_empty_profile_still_describes_something():
    assert FounderContext(founder_id=1).describe()
