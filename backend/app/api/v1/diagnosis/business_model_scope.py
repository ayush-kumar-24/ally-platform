"""Whether the founder RUNS the operation their industry's questions assume.

A FIFTH AXIS, alongside `stage_scope`, `context_scope`, `industry_scope`,
`team_scope` and `revenue_scope`, and separate from industry for a reason
industry alone cannot express:

    industry        was this question written for someone else's FIELD?
    business model  was it written for someone else's KIND OF BUSINESS
                    inside the same field?

Three founders tick Healthcare. One runs a physiotherapy clinic, one makes a
medical device, one sells booking software to clinics. They share a question
bank, and 21 of those questions are written for the first one only -- "Out of
100 patients, how many use you a second time?", "How much of your week goes on
clinical work?", "Is there a maintenance calendar for your fleet?" put to
somebody with no vehicles. The same split runs through twelve industries: a
restaurant and a packaged-food maker and a kitchen-software company all pick
Food & Beverage, which is the largest group of all at 29 questions.

WITHHELD, NOT REWORDED, AND THAT ORDER MATTERS. The first attempt reworded 64 of
these: patients became customers, guests became customers, dish and menu became
item and range. It worked and it was wrong. Specificity is the product -- a
homestay owner reading "Do you ask happy guests to leave a review?" is
understood, and reading "happy customers" could be any business alive -- and the
founder who prompted the fix is the minority, since most people who pick
Healthcare ARE a clinic. Rewording for everybody protected the exception by
flattening the majority. Fifteen questions kept their rewording, because there
the premise was a PLACE or a ROLE and the industry's vocabulary survived losing
it (migration a3f7b21c6d84). The other 49 got their vivid wording back and are
withheld here instead, together with the 27 that could never have been reworded
at all.

WHAT THIS READS, AND WHY IT IS A GUESS. `founders.product_description`, which
every founder fills in -- 25 of 25 rows, averaging 121 characters -- and which
says what they sell in their own words.

No column states the fact this module needs. `founders.business_model` sounds
like it would, and does not: its CHECK limits it to B2B, B2C, B2B2C,
marketplace, D2C and other, which is the SALES model -- who you bill -- and a
clinic and a clinic-software company are both B2B. It is also NULL in every row,
never having been asked for. So the choice was between adding an onboarding
question, which is reliable and costs a step, and reading the description, which
costs nothing and is sometimes wrong. This module reads the description, so
every decision it makes has to be safe when wrong.

SO IT RECOGNISES ONE THING, DELIBERATELY: that the founder's CUSTOMER is a
business of the trade. "Appointment booking and reminders for small clinics" --
you do not sell to clinics if you are the clinic. A second, narrower test
catches the descriptions that name a product category but no customer at all
("AI-powered SaaS that helps businesses diagnose problems"). Everything else,
including every case the text leaves ambiguous, reads as False and is asked
everything, exactly as today.

WHAT IT THEREFORE DOES NOT CATCH, stated plainly rather than discovered later.
It cannot reliably tell a packaged-food maker from a restaurant. Both say they
make food, and one real description reads "Home-style North Indian tiffin meals:
14 dishes" -- where "dish" and "menu" are precisely right -- while another reads
"hand-made Indian sweets and bars", where "menu" is wrong and no keyword
separates them. Keyword screening over this bank has been wrong in both
directions twice already (d4a1f8c62b73, a6f3d2c81b47), so that distinction is
left to an onboarding question if it ever earns one, rather than guessed here.
A packaged-food founder still sees a few questions written for a venue.

FAILING OPEN IS THE WHOLE SAFETY MODEL. Unknown admits, unreadable admits,
ambiguous admits, and a gate that would empty the candidate set admits. Being
asked one question you cannot answer is a bad moment. Having your diagnosis
quietly shrink because a regex misread your own description is worse, and you
would never know it happened.
"""

from __future__ import annotations

import re
from typing import Any

from app.core.logger import logger

#: Words a founder uses for a thing they BUILT AND SELL to other businesses.
#: Narrow on purpose: each names a category of product, not a way of working, so
#: "we use software to manage bookings" cannot match on this alone.
_TOOLING = (
    r"saas|software|platform|app|application|crm|erp|api|dashboard|portal"
    r"|marketplace|tool|toolkit|plugin|extension|integration|module"
)

#: A BUSINESS OF A TRADE, named as somebody the founder sells to. This is the
#: signal that actually works, and the tooling list above is not.
#:
#: Found the hard way. A real founder selling a booking product to physiotherapy
#: clinics describes it as "Appointment booking and reminders for small clinics"
#: -- no "software", no "SaaS", no "app", nothing from `_TOOLING` at all. Most
#: founders write what their product DOES, not which category it belongs to. So
#: what identifies a supplier is not the word for their product; it is that
#: their CUSTOMER is a business of the trade. You do not sell to clinics if you
#: are the clinic.
#:
#: WHAT IS DELIBERATELY NOT IN THIS LIST: manufacturer, distributor, brand,
#: developer, retailer-as-"seller", and every other noun that names a business
#: in SOME trade without naming one in the trade whose questions are at stake. A
#: real description reads "B2B line-haul and warehousing for manufacturers and
#: distributors across four cities" -- a logistics operator who owns warehouses
#: and trucks, and whose customers happen to be businesses. Putting
#: "manufacturers" in this list would strip that founder's fleet and warehouse
#: questions, which is the exact harm this module exists to prevent, inflicted
#: from the other direction.
_TRADE_BUSINESSES = (
    r"clinics?|hospitals?|labs?|laboratories|practices?|doctors?|physicians?"
    r"|dentists?|pharmacies|pharmacists?|nursing homes?|diagnostic centres?"
    r"|diagnostic centers?|physiotherapists?|physios?"
    r"|restaurants?|cafes?|caf\u00e9s?|cloud kitchens?|qsrs?|eateries|eatery"
    r"|bakeries|bakery|caterers?|canteens?|food outlets?"
    r"|hotels?|homestays?|resorts?|hostels?|guest ?houses?|tour operators?"
    r"|travel agents?|travel agencies|travel agency"
    r"|retailers?|kirana stores?|kiranas?|supermarkets?|grocers?"
    r"|couriers?|transporters?|fleets?|3pls?|freight forwarders?"
    r"|importers?|exporters?|wholesalers?"
    r"|schools?|colleges?|institutes?|coaching centres?|coaching centers?"
    r"|universities|university|academies|academy|tutors?"
    r"|builders?|contractors?|brokers?|real ?estate agents?"
    r"|salons?|parlours?|parlors?|gyms?|studios?"
)

#: The shape of SELLING to them. The preposition is required, so merely
#: mentioning hotels in passing cannot match -- it has to be who you sell to.
_SELLS_TO_TRADE = re.compile(
    rf"\b(for|to|used by|serving|serves?|sells? to|supplying|supplies|helps?"
    rf"|helping|built for|made for)\b[^.]{{0,40}}?\b({_TRADE_BUSINESSES})\b",
    re.I,
)

#: The older, narrower signal, kept for the descriptions that name a product
#: category but no customer: "AI-powered SaaS that helps businesses diagnose
#: problems" names no trade at all, and is still unmistakably not an operator.
#: The infinitive after "to" that makes it a PURPOSE rather than a customer.
#: "Software to stop paying commission" is a hotel describing why it built a
#: thing; "software to clinics" is somebody selling one. Without this the first
#: reads as the second, and a real hotel loses its guest questions.
_PURPOSE = (
    r"stop|save|avoid|reduce|cut|manage|run|handle|track|speed|automate|keep"
    r"|make|help|let|get|do|take|free|replace|improve|simplify|organise|organize"
)

_SELLS_TOOLING = re.compile(
    rf"\b({_TOOLING})\b[^.]{{0,60}}?\b(for|to|used by)\b(?!\s+({_PURPOSE})\b)"
    rf"|\bb2b\b[^.]{{0,40}}?\b({_TOOLING})\b"
    rf"|\b({_TOOLING})\b[^.]{{0,40}}?\bthat helps\b"
    rf"|\bhelps?\b[^.]{{0,40}}?\b({_TOOLING})\b",
    re.I,
)

#: Said by somebody who RUNS the operation, and strong enough to overrule both
#: tests above. A founder who writes "we run two clinics and sell our scheduling
#: software to other practices" is an operator who also sells tooling, and every
#: operator question is still theirs.
#:
#: The possessives matter as much as the verbs. "Our rooms", "our guests", "our
#: patients" are things only an operator has, and leaving them out let one real
#: shape through: "We use software to manage our bookings and keep our rooms
#: full" is a hotel, and it was read as a software company.
_RUNS_IT = re.compile(
    r"\b(we|i)\s+(run|runs|operate|operates|own|owns)\b"
    r"|\bour\s+(clinic|clinics|kitchen|kitchens|restaurant|restaurants|shop|shops"
    r"|store|stores|outlet|outlets|branch|branches|factory|warehouse|fleet"
    r"|salon|salons|hotel|hotels|practice|lab|labs"
    r"|rooms?|tables?|guests?|patients?|diners?|menu|covers|chefs?|drivers?"
    r"|riders?|vehicles?|staff|crew|premises|sites?)\b",
    re.I,
)

#: A BUYER of software, not a seller of it. The difference between "software for
#: clinics" and "we use software to run our clinic" is the whole classification,
#: and getting it backwards is the costly direction: the clinic silently loses
#: every question written for a clinic and nobody can see that it happened.
_USES_TOOLING = re.compile(
    rf"\b(we|i)\s+(use|uses|used|using|run on|built on|work with)\b"
    rf"[^.]{{0,40}}?\b({_TOOLING})\b"
    rf"|\b({_TOOLING})\b[^.]{{0,30}}?\bto\s+(manage|run|handle|track)\s+our\b"
    # Building a tool FOR YOURSELF is using one. "We built our own booking
    # software to stop paying commission" is a hotel, and was read as a
    # software company until this was added.
    rf"|\b(we|i)\s+(built|build|made|wrote|developed)\b[^.]{{0,30}}?\bour own\b"
    rf"|\bour own\b[^.]{{0,20}}?\b({_TOOLING})\b",
    re.I,
)

#: The description OPENS by naming what the founder is. "A 40-room hotel", "A
#: physiotherapy clinic in Pune", "A six-room homestay" -- a supplier does not
#: introduce itself as the thing it sells to. Checked only near the start, so a
#: software company that mentions hotels later is unaffected.
_IS_ONE = re.compile(
    rf"^\W*(a|an|the)?\s*[^.]{{0,44}}?\b({_TRADE_BUSINESSES})\b",
    re.I,
)


def sells_tooling_into_industry(founder: Any) -> bool:
    """Whether this founder's own description says they sell software or a
    platform to businesses in their industry, rather than running one.

    False for everything else, including an empty, missing or unreadable
    description -- see the module docstring on why the uncertain answer is
    always the admitting one.
    """
    text = getattr(founder, "product_description", None)
    if not isinstance(text, str):
        return False
    text = text.strip()
    if len(text) < 12:                    # too short to carry the signal
        return False
    if _RUNS_IT.search(text) or _USES_TOOLING.search(text):
        return False

    sells_to_trade = bool(_SELLS_TO_TRADE.search(text))

    # Order matters here. "Fee collection and attendance for schools and
    # coaching centres" opens with a trade business too, and is a supplier --
    # the preposition is the whole difference between naming your CUSTOMER and
    # naming YOURSELF. So the self-description only counts when nothing says
    # the trade is being sold to.
    if not sells_to_trade and _IS_ONE.search(text):
        return False

    return bool(sells_to_trade or _SELLS_TOOLING.search(text))


def can_answer(question: Any, sells_tooling: bool) -> bool:
    """Whether a founder may be asked this question.

    Two independent flags, both read defensively so a question that cannot say
    whether it carries one simply does not:

    `requires_operating_role` -- the question's subject is the industry's own
    operation: a kitchen, a clinical rota, a fleet, patients, guests.

    `requires_multiple_locations` -- the question's subject is a SECOND site.
    Withheld on the same signal for now, because a software company has no sites
    at all. It is a separate flag so that the day a location count is collected,
    the five questions that need it can be gated properly without disturbing the
    other seventy-one.
    """
    if not sells_tooling:
        return True
    if getattr(question, "requires_operating_role", False):
        return False
    if getattr(question, "requires_multiple_locations", False):
        return False
    return True


def gate(candidates: list, founder: Any) -> list:
    """Drop the questions written for an operation this founder does not run.

    Degrades exactly like `team_scope.gate` and `revenue_scope.gate`: three
    separate ways to end up not gating -- a description that does not say, a
    question with no flag, or a gate that would empty the set -- and every one
    of them admits the question.

    Never returns empty when it was given a non-empty set.
    """
    if not candidates:
        return candidates

    try:
        sells_tooling = sells_tooling_into_industry(founder)
    except Exception:                                      # noqa: BLE001
        logger.warning(
            "Business-model inference failed; leaving the set ungated",
            extra={"stage": "business_model_scope"},
        )
        return candidates

    if not sells_tooling:
        return candidates

    kept = [q for q in candidates if can_answer(q, sells_tooling)]

    if not kept:
        logger.warning(
            "Business-model gate matched no candidate question; leaving the set "
            "ungated rather than ending the diagnosis",
            extra={
                "stage": "business_model_scope",
                "candidates": len(candidates),
            },
        )
        return candidates

    if len(kept) != len(candidates):
        logger.info(
            "diagnosis gated on business model",
            extra={
                "stage": "business_model_scope",
                "withheld": len(candidates) - len(kept),
                "candidates": len(candidates),
            },
        )
    return kept
