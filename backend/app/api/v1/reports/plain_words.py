"""The words a founder reads. One list, so every surface says the same thing.

A user told us the reports and the diagnosis are hard to understand. The
temptation is to rewrite a prompt, and it would not have worked: almost none of
the hard words come from the model. They are hardcoded sentences in
document.py, templates in narrator.py, and stored content in readiness_pillars
-- and the model, handed facts full of "pillar", "band" and
"confirmation_status", simply repeats them back.

So this module holds the founder-facing vocabulary and every surface reads it:
the HTML report, the PDF (same builder), the narrator's templates, and the
prompts, which are given plain labels rather than internal ones.

INTERNAL NAMES DO NOT CHANGE. `readiness_pillars.score_bands[].level` still
says "Critical Gap", because code matches on it -- business_health._BOTTOM_BAND
decides whether a red flag may fire, and renaming the row would turn every red
flag off silently. The level stays the key; BAND_WORDS is what gets printed.
Same for pillar names, category names and root-cause labels: they are
identifiers in the catalogue and captions on the page, and only the caption
changes.

ADDING A TERM. Put it here, use it everywhere, and if it is a word a founder
should never see, add it to BANNED as well --
test_plain_language.py fails on any BANNED word appearing in a rendered report,
which is what stops the jargon growing back one sentence at a time.
"""

from __future__ import annotations

#: Score-level `level` -> what the founder reads.
#:
#: "Critical Gap" was the worst of them: it reads as a verdict on the person,
#: and at the bottom of a band it is often just "you have not started this
#: yet". The replacements say where something stands without grading anybody.
BAND_WORDS = {
    "Critical Gap": "Not working yet",
    "Needs Attention": "Needs work",
    "Developing": "Coming along",
    "Strong": "Working well",
}

#: How settled a finding is. The old words were "Early / Moderate / High
#: confidence", which reads like a mark out of ten on the founder.
CONFIDENCE_WORDS = {
    "High": "confident",
    "Moderate": "fairly sure",
    "Early": "a first read",
}

#: Root-cause confirmation status -> plain words. "unconfirmed" is the ordinary
#: state of every finding here (confirming it needs the next steps to come
#: back), and it read as though something had failed.
STATUS_WORDS = {
    "unconfirmed": "not tested yet",
    "not tested": "not tested yet",
    "confirmed": "tested and confirmed",
    "ruled out": "ruled out",
}

#: Words that must never reach a founder, mapped to what to say instead. The
#: mapping is documentation for whoever writes the next sentence; the enforcement
#: is BANNED below.
PLAIN_WORDS = {
    "pillar": "area of your business",
    "pillars": "areas of your business",
    "readiness pillar": "area",
    "dimension": "area",
    "dimensions": "areas",
    "band": "where you stand",
    "score band": "where you stand",
    "root cause": "what is really holding you back",
    "hypothesis": "best guess",
    "hypotheses": "best guesses",
    "mechanism": "one thing",
    "signal": "",                      # cut it, never replaced
    "confirmation status": "whether we have tested it",
    "normalised risk": "",
    "Section H": "",                   # an internal section number
    "Psychological State Note": "how you are doing",
}

#: Checked against the rendered report by test_plain_language.py. Lowercased
#: substring match, so "Pillars" and "pillar." are both caught.
#:
#: NOT a superset of PLAIN_WORDS' keys. Three of those words are legitimate in a
#: founder's own quoted answer -- a founder may well say "our runway" or write
#: the word "signal" -- and the test only reads the report's OWN sentences, so
#: the list stays about what the report says in its own voice.
BANNED = (
    "pillar",
    "score band",
    "root cause",
    "hypothes",          # hypothesis / hypotheses
    "mechanism",
    "confirmation_status",
    "confirmation status",
    "normalised risk",
    "section h",
    "psychological state note",
    "unconfirmed",
    "not_applicable",
)


def band_words(level: str | None) -> str:
    """Plain words for a score level, or the level itself if it is not ours.

    Falls through rather than blanking, because score_bands is content the team
    edits: a level added there tomorrow should appear on the page as written,
    not vanish because this map has not caught up.
    """
    if not level:
        return ""
    return BAND_WORDS.get(str(level).strip(), str(level))


def confidence_words(strength: str | None) -> str:
    """Plain words for High / Moderate / Early."""
    if not strength:
        return ""
    return CONFIDENCE_WORDS.get(str(strength).strip(), str(strength))


def status_words(status: str | None) -> str:
    """Plain words for a confirmation status, e.g. 'unconfirmed'."""
    if not status:
        return ""
    key = str(status).replace("_", " ").strip().lower()
    return STATUS_WORDS.get(key, key)


#: Fact-row keys -> the label a founder reads above the value.
#:
#: _facts_html builds a label by title-casing the key, which is how "Red Flag
#: Pillars", "Overall Band" and "Confirmation Status" ended up as headings on
#: the page. The key stays as it is -- it is the narrative's own contract and
#: the frontend reads it too -- and only the caption changes.
#:
#: A key with no entry keeps the title-cased fallback, so a fact added later
#: appears rather than disappearing.
FACT_LABELS = {
    "red_flag_pillars": "Needs your attention first",
    "overall_band": "Where you stand",
    "band": "Where you stand",
    "band_description": "What this usually means",
    "confirmation_status": "Have we tested it",
    "finding_status": "Have we tested it",
    "primary_finding": "The main thing",
    "pillars": "Areas of your business",
    "pillars_assessed": "Areas we looked at",
    "pillars_total": "Areas in total",
    "dimensions_in_scope": "Parts we looked at",
    "dimensions_total": "Parts in total",
    "diagnosis_answers": "Questions you answered",
    "categories": "Parts of your business",
    "confirm_steps": "Steps to find out",
    "confirm_actions": "Steps to find out",
    "next_actions": "What to do next",
    "intervention_ids": "",            # internal ids, never a caption
    "core_motivation": "What drives you",
    "founder_readiness_band": "How you are doing",
    "strength_evidence": "What is already working",
}


def fact_label(key: str) -> str:
    """The founder-facing caption for a fact key.

    Returns "" for a key that should not be captioned at all, which the caller
    treats as "skip this row".
    """
    name = str(key or "")
    if name in FACT_LABELS:
        return FACT_LABELS[name]
    return name.replace("_", " ").strip().title()


#: The writing rule every report prompt carries. Lifted from the support bot's
#: (app/support_bot/prompts.py), which a founder-facing surface already had and
#: the report did not -- the report prompts said only "warm, plain sentences",
#: and were then handed facts full of "pillar", "band" and
#: "confirmation_status", so the model repeated them back.
#:
#: The banned list is NOT belt-and-braces for the prompt. The model cannot see
#: what it is not given, so the real fix is upstream -- plain labels in the
#: facts. This is here for the words it would reach for on its own.
HOW_TO_WRITE = (
    "HOW TO WRITE:\n"
    "- Very simple, easy English. Short sentences. Common everyday words.\n"
    "- No jargon, no idioms, no marketing voice.\n"
    "- Say 'you' and 'your business'. Never 'the founder' or 'the user'.\n"
    "- Never use these words: pillar, band, score band, root cause, "
    "hypothesis, mechanism, signal, dimension, confirmation status, "
    "unconfirmed, normalised, Section H. Say what they mean instead: "
    "'area of your business', 'where you stand', 'what is really holding you "
    "back', 'our best guess', 'one thing', 'part of your business', "
    "'not tested yet'.\n"
    "- Do not name a number that is not in the facts you were given.\n"
    "- Write as if to someone running their first business, who is smart and "
    "busy and has never read a consulting report."
)


#: Slot keys the model must never be shown, because there is nothing it can say
#: with them and every one of them has leaked into prose.
#:
#: "section_h_text" and "section" are the worst: a section NUMBER from the
#: internal spec, which reached a live report as "The report will include
#: Section H (Psychological State Note)". The text under that key is still
#: narrated -- it is renamed, not dropped, so the founder keeps the content
#: without the filing reference.
#: `red_flag_note` is in here for a different reason from the rest: it is not
#: noise, it is the pillar's SCORING RULE, written for whoever tunes the engine
#: -- "A score below 35% in this pillar triggers Section H (Psychological State
#: Note) in the Founder Clarity Report regardless of all other scores." The
#: frontend already filters it out of founder-facing facts and the document does
#: too; the prompt was the one reader still being handed it, and a model given
#: that sentence can only paraphrase it back.
_HIDDEN_SLOTS = frozenset({"section", "trigger", "psychology_flagged",
                           "separate_identity", "exposes_numeric_scores",
                           "narrator", "cta", "degraded", "provisional",
                           "red_flag_note"})

#: Slot keys renamed before the model sees them. Same idea as FACT_LABELS, for
#: a different reader: the page gets a caption, the model gets a key it can
#: safely echo. A key is a WORD to a language model -- handed
#: "confirmation_status": "unconfirmed" it writes "confirmation status:
#: unconfirmed", because that is what it was given.
_SLOT_KEYS = {
    "section_h_text": "how_you_are_doing",
    "red_flag_pillars": "areas_to_start_with",
    "overall_band": "where_you_stand",
    "band": "where_you_stand",
    "band_description": "what_this_usually_means",
    "pillars": "areas_of_your_business",
    "pillars_assessed": "areas_we_looked_at",
    "pillars_total": "areas_in_total",
    "weakest_pillar": "area_that_needs_most_work",
    "confirmation_status": "have_we_tested_it",
    "finding_status": "have_we_tested_it",
    "root_causes": "what_might_be_holding_you_back",
    "primary_finding": "the_main_thing",
    "dimensions_in_scope": "parts_we_looked_at",
    "dimensions_total": "parts_in_total",
    "confirm_steps": "steps_to_find_out",
    "solve_steps": "steps_to_fix_it",
    "founder_readiness_band": "how_you_are_doing",
}

#: Slot VALUES that are internal vocabulary. The band levels are the ones that
#: matter: handed "Critical Gap" the model writes "Critical Gap".
_SLOT_VALUES = {**BAND_WORDS, **{k: v for k, v in STATUS_WORDS.items()}}


def plain_slots(slots):
    """The slots, with internal keys and values swapped for founder words.

    Applied where the prompt is built rather than where the slots are made,
    because the template narrator and the document both need the original keys
    -- the narrative's slot contract is read by the frontend too. Only what
    reaches the model changes.

    Recurses through lists and dicts, since `pillars` is a list of dicts each
    carrying its own `band` and `band_description`.
    """
    if isinstance(slots, dict):
        out = {}
        for key, value in slots.items():
            name = str(key)
            if name in _HIDDEN_SLOTS:
                continue
            out[_SLOT_KEYS.get(name, name)] = plain_slots(value)
        return out
    if isinstance(slots, (list, tuple)):
        return [plain_slots(v) for v in slots]
    if isinstance(slots, str):
        return _SLOT_VALUES.get(slots.strip(), slots)
    return slots
