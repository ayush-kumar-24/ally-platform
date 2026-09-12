"""Pricing a turn before it runs, and what is left to price it against.

The behaviour these guard was added after a founder ended a day at 9,894 tokens
against an 8,000 ceiling -- admitted because the only test was `used < limit`,
and charged the real cost afterwards, when it was too late to refuse.
"""

from app.plans.tokens import estimate_tokens, turn_cost_estimate


# --- the estimate -----------------------------------------------------------


def test_empty_and_missing_text_cost_nothing():
    assert estimate_tokens() == 0
    assert estimate_tokens("") == 0
    assert estimate_tokens(None, None) == 0


def test_fragments_are_summed_before_rounding_not_after():
    """A prompt is a system part and a user part, and both are billed. Rounding
    each one up separately would drift by the number of fragments -- small here,
    and exactly the kind of small that turns a budget check into a lie."""
    assert estimate_tokens("a" * 10, "b" * 10) == estimate_tokens("c" * 20)


def test_the_estimate_is_biased_high():
    """Deliberate, and the direction matters: under-estimating lets the overshoot
    back in, over-estimating only refuses a turn slightly early. English runs
    ~4 characters per token, so 1,000 characters must price above 250."""
    assert estimate_tokens("x" * 1000) > 250


def test_longer_text_never_costs_less():
    assert estimate_tokens("x" * 100) <= estimate_tokens("x" * 200)


# --- the whole turn ---------------------------------------------------------


def test_a_turn_costs_its_prompt_plus_the_whole_reply_cap():
    """The reply is priced at its ceiling, not at anything typical: a budget check
    is only worth making if its answer holds for the reply that actually turns up,
    and the only length guaranteed not to be exceeded is the one the provider was
    told not to exceed."""
    prompt = estimate_tokens("system text", "user text")
    assert turn_cost_estimate("system text", "user text", 800) == prompt + 800


def test_a_zero_reply_cap_prices_only_the_prompt():
    assert turn_cost_estimate("abc", "def", 0) == estimate_tokens("abc", "def")


def test_a_negative_reply_cap_cannot_discount_the_prompt():
    """Defensive: a misconfigured cap must not make a turn look cheaper than its
    prompt, which would admit exactly the turns this check exists to refuse."""
    assert turn_cost_estimate("abc", "def", -5000) == estimate_tokens("abc", "def")


def test_an_empty_turn_still_costs_the_reply_cap():
    assert turn_cost_estimate(None, None, 800) == 800
