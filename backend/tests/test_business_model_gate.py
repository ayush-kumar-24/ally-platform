"""Business-model gating: whether the founder runs the operation the question
assumes.

An industry is not a business model. Three founders tick Healthcare -- a
physiotherapy clinic, a medical device maker, and somebody selling booking
software to clinics -- and share one question bank, 21 of whose questions are
written for the first only. The same split runs through twelve industries, and
Food & Beverage is the largest at 29: a restaurant, a packaged-food maker and a
kitchen-software company all pick it.

WITHHELD, NOT REWORDED, which is what these tests mostly protect. Rewording was
tried first on 64 questions and it flattened the product: "Do you ask happy
guests to leave a review?" became "happy customers", which could be any business
alive, and the founder it helped is the minority. 49 of those got their wording
back and are gated here instead.

THE CLASSIFICATION IS A GUESS, so the tests are weighted towards the direction
that costs least when it is wrong. There is no column stating the business model
-- `founders.business_model` is the SALES model, B2B or D2C, and a clinic and a
clinic-software company are both B2B -- so this reads
`founders.product_description`, which every founder fills in. Guessing
"operator" wrongly asks somebody one question they cannot answer. Guessing
"supplier" wrongly strips a clinic of every question written for a clinic, and
nobody can see that it happened. So the asymmetry is the design, and most of
what follows checks the second kind never happens.
"""

from types import SimpleNamespace

import pytest

from app.api.v1.diagnosis.business_model_scope import (
    can_answer,
    gate,
    sells_tooling_into_industry,
)


def _f(description):
    return SimpleNamespace(founder_id=1, product_description=description)


def _q(qid, *, operating=False, locations=False):
    return SimpleNamespace(
        question_id=qid,
        requires_operating_role=operating,
        requires_multiple_locations=locations,
    )


# --- recognising a supplier -------------------------------------------------

#: Real and realistic descriptions of somebody who sells INTO a trade.
SELLS_INTO_A_TRADE = [
    # The one that drove the design. No "software", no "SaaS", no "app" -- most
    # founders write what their product DOES, not its category, so a word list
    # of product categories missed it entirely.
    "Appointment booking and reminders for small clinics",
    "B2B SaaS for dental clinics: appointments, patient records, billing.",
    "A booking and reminder tool for physiotherapy clinics.",
    "Platform used by small hotels to manage direct bookings.",
    "Kitchen management software for restaurant chains.",
    "We supply uniforms and linen to hotels and resorts across Kerala.",
    "Inventory tracking built for kirana stores.",
    "Fee collection and attendance for schools and coaching centres.",
    # Names a product category and no trade at all; still not an operator.
    "AI-powered SaaS that helps businesses diagnose problems and turn "
    "insights into actionable growth decisions.",
]


@pytest.mark.parametrize("description", SELLS_INTO_A_TRADE)
def test_a_supplier_to_the_trade_is_recognised(description):
    assert sells_tooling_into_industry(_f(description)) is True


# --- never mistaking an operator for a supplier -----------------------------

#: The costly direction. Each of these runs the operation, and each contains
#: something that a looser test would have read as selling into the trade.
OPERATES_THE_BUSINESS = [
    # Sells tooling AND runs clinics. Every operator question is still theirs.
    "We run two clinics and also sell our scheduling software to other practices.",
    # Uses software; does not sell it. The distinction is the whole job.
    "We use software to manage our bookings and keep our rooms full.",
    "A 40-room boutique hotel in Goa. We use a channel manager app for distribution.",
    "Dental practice with a CRM to manage our patients.",
    # Customers are businesses, but not businesses of THIS trade. Putting
    # "manufacturers" in the trade list would strip this founder's fleet and
    # warehouse questions -- the same harm, inflicted from the other side.
    "B2B line-haul and warehousing for manufacturers and distributors "
    "across four cities, sold on reliability rather than lowest rate.",
    "A 31-year-old auto-component workshop supplying tier-1 manufacturers.",
    # Makes the thing. "Dishes" here is the founder's own menu, not a customer.
    "Home-style North Indian tiffin meals: 14 dishes, sold mostly through "
    "Swiggy and Zomato.",
    "A range of hand-made Indian sweets and bars -- ragi-peanut, besan-jaggery.",
    "Sells small-batch banana chips online, direct to customers.",
    "Our kitchen supplies corporate canteens across Pune.",
    # Sells franchises of a parlour, which still means setting its standards.
    "A franchised beauty parlour -- hair, skin, bridal -- sold to women who "
    "want their own business, with training, standards and supply included.",
    "Clean-beauty skincare: 19 SKUs across cleansers, serums and moisturisers, "
    "sold D2C and through salons.",
    "Nothing built yet. Stream and career guidance for parents of 9th-10th "
    "standard students.",
]


@pytest.mark.parametrize("description", OPERATES_THE_BUSINESS)
def test_an_operator_is_never_mistaken_for_a_supplier(description):
    assert sells_tooling_into_industry(_f(description)) is False


# --- failing open -----------------------------------------------------------

@pytest.mark.parametrize("description", [
    None, "", "   ", "shop", "early days", 7, 2.5, object(), ["a list"],
])
def test_an_unusable_description_reads_as_operator(description):
    """Which admits everything. A founder whose description we cannot read is
    not narrowed at all -- the same reading `team_scope` gives an unknown team
    size and `context_scope` gives an unrecorded problem code."""
    assert sells_tooling_into_industry(_f(description)) is False


def test_a_founder_object_without_the_field_is_admitted():
    assert sells_tooling_into_industry(SimpleNamespace(founder_id=1)) is False
    bare = SimpleNamespace(question_id=1)
    assert gate([bare], SimpleNamespace(founder_id=1)) == [bare]


def test_a_question_that_cannot_say_whether_it_is_flagged_is_admitted():
    """The engine's ranking terms all read a question defensively; so must this.
    A candidate with no flags has none."""
    bare = SimpleNamespace(question_id=1)
    assert can_answer(bare, sells_tooling=True) is True


def test_the_gate_never_empties_a_non_empty_set():
    """Ending a founder's diagnosis early over a classification is worse than
    asking one question they cannot answer."""
    all_operator = [_q(1, operating=True), _q(2, operating=True)]
    kept = gate(all_operator, _f("Appointment booking and reminders for small clinics"))
    assert kept == all_operator


def test_a_classifier_that_raises_does_not_stop_the_diagnosis():
    class Exploding:
        founder_id = 1

        @property
        def product_description(self):
            raise RuntimeError("boom")

    questions = [_q(1, operating=True), _q(2)]
    assert gate(questions, Exploding()) == questions


# --- the gate itself --------------------------------------------------------

def test_an_operator_keeps_every_question():
    questions = [_q(1), _q(2, operating=True), _q(3, locations=True)]
    assert gate(questions, _f("A 40-room boutique hotel in Goa.")) == questions


def test_a_supplier_loses_only_the_flagged_questions():
    neutral, operating, locations = _q(1), _q(2, operating=True), _q(3, locations=True)
    kept = gate(
        [neutral, operating, locations, _q(4)],
        _f("Appointment booking and reminders for small clinics"),
    )
    assert operating not in kept
    assert locations not in kept
    assert neutral in kept


def test_the_two_flags_are_read_independently():
    """`requires_multiple_locations` is a separate flag because the signal
    gating it today is a stand-in: a single-outlet restaurant runs the operation
    and still has no second site. Keeping them apart is what lets those five be
    re-gated on a real location count without disturbing the other 71."""
    supplier = True
    assert can_answer(_q(1, operating=True), supplier) is False
    assert can_answer(_q(2, locations=True), supplier) is False
    assert can_answer(_q(3), supplier) is True
