"""The read Ally forms without a model.

This is the floor, not the ceiling: it runs when the model is unconfigured,
slow, or failing, and a founder must never reach the "Reading between the
lines" screen and find an error there.

It is rule-based but not a template. Every sentence is chosen by what the
founder actually answered, and the interesting ones come from combinations --
a first-time founder naming Hiring and Leadership together is a different read
from a serial founder naming Cash flow, and neither is the generic line.
"""

from app.api.v1.impression.facts import FounderFacts, prose_list
from app.api.v1.impression.schemas import FirstImpression

# What each stage is really about, used to say something true rather than
# repeating the stage name back.
STAGE_FOCUS = {
    "Ideation": "choosing what deserves your attention before you commit to it",
    "Validation": "finding out whether anyone actually wants this",
    "Prototype / MVP": "getting a first version into real hands",
    "Early Traction": "turning first customers into a repeatable pattern",
    "Growth / Scaling": "making what already works survive more of itself",
    "Expansion": "adding a second thing without breaking the first",
    "Maturity": "protecting what works while it still can change",
    "Exit": "making the business make sense without you in it",
}

# Read of the pressure a founder named, by bucket.
PRESSURE_READ = {
    "delegation": "the load sits with you more than it sits with the team",
    "money": "the runway is close enough to shape the decisions",
    "demand": "getting enough of the right people to notice",
}

INSTINCT_BY_KIND = {
    "delegation": "Your instinct when the team is stretched is to absorb the work yourself first.",
    "money": "Your instinct when money is tight is to cut before you ask for help.",
    "demand": "Your instinct when growth stalls is to push harder on what already works.",
}


def _bullets(f: FounderFacts) -> list[str]:
    out: list[str] = []

    focus = STAGE_FOCUS.get(f.stage)
    if focus:
        out.append(f"Placed you at {f.stage} — where the work is {focus}")
    elif f.stage:
        out.append(f"Placed you at {f.stage}")

    if f.problem:
        who = prose_list(f.audience) or "the people you serve"
        out.append(f"Heard the problem you keep returning to, and who it costs: {who}")
    elif f.building:
        out.append("Heard what you're building, in your own words")

    kinds = f.challenge_kinds()
    if f.challenges:
        reads = [PRESSURE_READ[k] for k in ("delegation", "money", "demand") if k in kinds]
        if reads:
            out.append(f"Flagged where the pressure actually sits — {reads[0]}")
        else:
            out.append(f"Flagged the pressure you named: {prose_list(f.challenges)}")

    if f.why:
        out.append("Noted why this one matters to you, which is not a small detail")

    if f.feeling:
        pace = "so I'll keep the pace kind" if f.under_strain else "so I'll keep up"
        out.append(f"Read where you're at today as {f.feeling.lower()} — {pace}")

    # Four reads well; more starts to feel like a list rather than a thought.
    return out[:4] or ["Read what you told me, and I'm ready to go deeper"]


def _read(f: FounderFacts) -> str:
    parts: list[str] = []

    if f.experience and f.stage:
        parts.append(f"You're a {f.experience.lower()} at {f.stage}")
    elif f.stage:
        parts.append(f"You're at {f.stage}")

    kinds = f.challenge_kinds()
    if "delegation" in kinds and f.experience in {"First-time founder", "Built one company"}:
        parts.append(
            "and the challenges you picked point the same way: the business is asking for "
            "more people than you currently have, and in the meantime you are the buffer"
        )
    elif "money" in kinds and "demand" in kinds:
        parts.append(
            "and you named both money and demand, which usually means the same problem "
            "wearing two faces — the runway is short because the pull isn't there yet"
        )
    elif kinds:
        pressure = prose_list([PRESSURE_READ[k] for k in ("delegation", "money", "demand") if k in kinds])
        parts.append(f"and the pressure you named is real: {pressure}")
    elif f.challenges:
        parts.append(f"and what's pulling at you is {prose_list(f.challenges).lower()}")

    sentence = ", ".join(p for p in parts if p).strip()
    sentence = (sentence + ".") if sentence and not sentence.endswith(".") else sentence

    tail = ""
    if f.goal_90 and f.vision:
        tail = (
            f" You want {f.goal_90.rstrip('.').lower()} in ninety days, on the way to "
            f"{f.vision.rstrip('.').lower()}. Those two need to point the same direction, "
            "and that's worth checking early."
        )
    elif f.goal_90:
        tail = f" The next ninety days are about {f.goal_90.rstrip('.').lower()}."

    why = ""
    if f.why:
        why = f" The reason underneath it is personal: {f.why.rstrip('.').lower()}."

    strain = ""
    if f.under_strain:
        strain = (
            " You also told me you're carrying this while feeling "
            f"{f.feeling.lower()}, which I'm not going to talk past."
        )

    out = (sentence + tail + why + strain).strip()
    return out or "I have your answers, and I'm ready to go deeper with you."


def _instinct(f: FounderFacts) -> str:
    kinds = f.challenge_kinds()
    for kind in ("delegation", "money", "demand"):
        if kind in kinds:
            return INSTINCT_BY_KIND[kind]
    if f.top_challenge:
        return (
            f"Your instinct when {f.top_challenge.lower()} gets heavy is to push through "
            "it alone rather than change the shape of the problem."
        )
    return "Your instinct when growth stalls is to push harder on what already works."


def derive_impression(f: FounderFacts) -> FirstImpression:
    """Assemble a read from the founder's answers. Never raises."""
    return FirstImpression(
        bullets=_bullets(f),
        read=_read(f),
        instinct=_instinct(f),
        source="derived",
    )
