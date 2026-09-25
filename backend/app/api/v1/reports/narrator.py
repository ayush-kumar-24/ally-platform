"""Section narrators -- the ONLY component that writes prose.

Contract: a narrator is handed one section's slots (engine facts) + tone guidance
and returns a human sentence or two. It must never introduce a number, score,
finding, name or claim that is not in the slots it was given. Facts stay
structured on the section; the prose sits alongside them.

`TemplateNarrator` is deterministic (default + the safe fallback): it composes
sentences purely from the slot values, so it cannot fabricate. `LLMSectionNarrator`
calls a model once per section with that section's slots only -- smaller context,
cannot leak facts between sections -- and falls back to the template on any error.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Callable, Protocol


_QUOTE_MAX_CHARS = 160


def _shorten(text: str, limit: int = _QUOTE_MAX_CHARS) -> str:
    """One short line out of a founder's answer.

    Founders type paragraphs into these boxes, and this narrator quotes them
    verbatim into a lead paragraph -- which is how the hero ends up a wall of
    text. Prefer the first sentence, because a first sentence is a whole
    thought and cutting mid-clause reads as a bug; fall back to a word-boundary
    cut only when that sentence is itself longer than the limit.
    """
    text = " ".join((text or "").split())
    if not text:
        return ""
    # Earliest terminator, not the first one in some fixed order: scanning
    # "." before "!" would return the second sentence of "Ship it! Then rest."
    ends = [i for stop in (". ", "! ", "? ") if (i := text.find(stop)) != -1]
    if ends and min(ends) + 2 <= limit:
        return text[: min(ends) + 1]
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0].rstrip(" ,;:-")
    return f"{cut}\u2026"


def _is_question(text: str) -> bool:
    """A stored "answer" that is actually the question it was asked.

    This is live in production data today: some `strengths_blind_spots` rows
    hold the prompt rather than the reply, and narrating one produces "A
    pattern worth naming: Tell me about the last time...". Dropping it costs a
    line; printing it costs the founder's trust in the whole report.
    """
    return " ".join((text or "").split()).endswith("?")


#: One Founder-DNA card's worth of text. Long enough for two plain sentences,
#: short enough that a dozen of them on one page still read as a summary.
_DIMENSION_SUMMARY_CHARS = 220


def _answer_text(value: Any) -> str:
    """A dimension's raw material as one string, minus any stored question.

    A dimension is either a single answer or a list of them (see
    generator._slots_and_facts); both arrive verbatim as the founder typed
    them, which is exactly why they need shortening before they are shown.
    """
    values = value if isinstance(value, (list, tuple)) else [value]
    parts = [
        " ".join(str(v).split())
        for v in values
        if isinstance(v, str) and str(v).strip() and not _is_question(v)
    ]
    return " ".join(parts)


def _json_object(raw: str) -> str:
    """The outermost {...} in a model reply, so a fenced or chatty response
    still parses. Returns the input unchanged when there is no object to find,
    letting the caller's own json error handling deal with it."""
    start, end = raw.find("{"), raw.rfind("}")
    return raw[start : end + 1] if 0 <= start < end else raw


@dataclass(frozen=True)
class ToneGuidance:
    persona: str | None                 # Validator / Compass / Auditor
    tone_prompt: str | None = None      # prompt_library stage tone text (LLM only)
    session_framing: str | None = None  # session_state_bands.report_framing_adjustment
    distress_protocol: str | None = None  # prompt_library distress protocol text


class SectionNarrator(Protocol):
    def narrate(self, section_key: str, slots: dict[str, Any], tone: ToneGuidance) -> str: ...


#: Spelled out so the prose reads as prose. Falls back to the digit for
#: anything outside the range, which cannot happen with six pillars.
_WORDS = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six"}


def _and_list(items: Sequence[str]) -> str:
    """"a", "a and b", "a, b and c" -- prose, not a comma-joined dump."""
    items = list(items)
    if len(items) <= 1:
        return items[0] if items else ""
    return f"{', '.join(items[:-1])} and {items[-1]}"


def _pillar_label(pillar: Mapping[str, Any]) -> str:
    """A pillar's name, qualified when the stage covers only part of it.

        Market Clarity
        Product & Execution (Execution Velocity only)
        Strategic Clarity (Plan-to-Vision Alignment and Prioritization Discipline only)

    Business DNA Part 3 scopes several pillars partially. At ideation, Product &
    Execution is one dimension of three, and Founder Readiness and Strategic
    Clarity are two of three; through Stage 0->1, Revenue Maturity is three of
    four and Team & Leadership two of three. Printing the bare pillar name over
    those readings overstates them -- "Product & Execution: Needs Attention"
    tells a pre-launch founder their product was assessed, when what was assessed
    was how fast they move.

    The qualifier names the dimensions rather than counting them ("1 of 3"),
    because a founder cannot act on a count. It uses Part 2's own wording, so the
    report and the document say the same words for the same thing.

    NO qualifier when the stage covers the whole pillar, which is the common case
    -- every pillar at Growth and above, and most of them earlier. Also none when
    the coverage is unknown (`dimensions_total` 0): an older report row stored
    before this existed, or a founder whose stage could not be resolved. Silence
    is right for both; a claim about coverage we cannot support is worse than no
    claim.
    """
    name = str(pillar.get("pillar_name") or "")
    covered = [str(d) for d in (pillar.get("dimensions_in_scope") or ())]
    total = int(pillar.get("dimensions_total") or 0)

    if not total or not covered or len(covered) >= total:
        return name
    return f"{name} ({_and_list(covered)} only)"


class TemplateNarrator:
    """Deterministic prose from slots only. Every number it emits comes verbatim
    from a slot value; it never computes or invents."""

    def narrate(self, section_key: str, slots: dict[str, Any], tone: ToneGuidance) -> str:
        fn = getattr(self, f"_{section_key}", None)
        return fn(slots, tone) if fn else ""

    def narrate_with_source(self, section_key, slots, tone) -> tuple[str, str]:
        return self.narrate(section_key, slots, tone), "template"

    def summarise_dimensions(self, dimensions: dict[str, Any]) -> dict[str, str]:
        """Shorten each Founder-DNA dimension to its first whole thought.

        Deterministic, so it cannot make the founder's own words plainer -- only
        a model can do that -- but it stops one card from carrying three
        paragraphs, which is the larger of the two problems.
        """
        out: dict[str, str] = {}
        for key, value in dimensions.items():
            text = _shorten(_answer_text(value), _DIMENSION_SUMMARY_CHARS)
            if text:
                out[key] = text
        return out

    # --- sections --------------------------------------------------------
    def _founder_summary(self, s, tone):
        name = s.get("founder_name") or "there"
        lead = {
            "Validator": "Here is what your answers say about where you stand.",
            "Compass": "Here is a read on your direction and what to focus on next.",
            "Auditor": "Here is a structured read on the business and where it stands.",
        }.get(tone.persona, "Here is your clarity report.")
        return f"{name}, {lead}"

    def _founder_dna(self, s, tone):
        # Archetype drives the lead sentence when present; the newer dimensions
        # (origin, vision, strengths/blind spots, stress response, communication
        # preference) each add at most one short, fact-only line so the template
        # fallback stays readable rather than a wall of quoted text -- the full
        # set is still visible as cards via `facts` regardless of what prose says.
        #
        # "Short" is now enforced by _shorten rather than merely intended. It was
        # intended here from the start and never applied, so founders who wrote
        # three paragraphs into the vision box got all three quoted back at them
        # in the report hero. An intention with no code behind it is not a limit.
        parts = []
        arch = s.get("archetype")
        if arch and arch.get("name"):
            # Archetype names already begin with "The" -- do not prepend an article.
            name, motiv = arch["name"], arch.get("core_motivation")
            motiv_txt = f", driven by {motiv.lower()}" if motiv else ""
            if arch.get("is_confident"):
                opener = {"Validator": "Your answers point clearly to",
                          "Auditor": "The pattern the data supports is"}.get(
                              tone.persona, "Your founder pattern reads clearly as")
                parts.append(f"{opener} {name}{motiv_txt}.")
            else:
                parts.append(
                    f"Your answers lean toward {name}{motiv_txt}, but the signal is "
                    "mixed -- treat this as a starting hypothesis to test, not a fixed label."
                )
        vision = s.get("vision")
        if vision:
            parts.append(
                "In your own words, this is what success looks like: "
                f'"{_shorten(vision)}"'
            )
        blind_spots = s.get("strengths_blind_spots")
        if blind_spots and not _is_question(blind_spots[0]):
            parts.append("A pattern worth naming: " + _shorten(blind_spots[0]))
        # purpose_mission gets the same one-line treatment as vision (both are
        # "why this matters" statements); the other 5 phase-2 dimensions stay
        # card-only here, same as origin/stress_response/communication_
        # preference above -- narrating all 9+ possible dimensions in prose
        # would be exactly the wall-of-text this fallback is written to avoid.
        purpose_mission = s.get("purpose_mission")
        if purpose_mission:
            parts.append(
                "On why this matters to you: "
                f'"{_shorten(purpose_mission[0])}"'
            )
        return " ".join(parts)

    def _psychological_note(self, s, tone):
        # Founder-facing sources ONLY: the Section H band description or the pillar
        # red-flag note (both authored for founders in readiness_pillars). Never
        # tone.session_framing -- that is a system directive, not founder-facing prose.
        body = s.get("section_h_text") or s.get("red_flag_note")
        sep = s.get("separate_identity")
        sep_txt = " The business has challenges. You are not those challenges." if sep else ""
        base = "A note on where you are right now, before anything about the business. "
        if body:
            return base + body + sep_txt
        if s.get("psychology_flagged"):
            return (base + "How you are doing as a founder is shaping how this session "
                    "went, and it is worth attending to first." + sep_txt)
        return ""

    def _business_dna(self, s, tone):
        # Bands + written descriptions -- never raw numbers.
        band = s.get("overall_band")
        # Under distress, business content is de-prioritised: a single gentle line,
        # no six-pillar audit at a moment the founder should not be pushed on it.
        if s.get("brief"):
            if not band:
                return ""
            return (f'A brief note on the business: overall it reads as "{band}". '
                    "There is more detail when you are ready for it -- it can wait.")
        parts = []
        if band:
            # NOT hardcoded "six". Stage scoping means an ideation founder is
            # assessed on four (Business DNA Part 3), and any stage can lose a
            # pillar the session gave too few answers to score. The total
            # renormalises onto what remains, so a fixed "across the six
            # readiness pillars" told the founder we had looked at pillars we
            # never asked them about.
            total = s.get("pillars_total") or 6
            assessed = s.get("pillars_assessed") or total
            scope = (
                f"Across all {_WORDS.get(total, total)} readiness pillars"
                if assessed >= total
                else f"Across the {_WORDS.get(assessed, assessed)} readiness "
                     f"pillars that apply at your stage"
            )
            subject = {"Auditor": "business health reads as",
                       "Validator": "where you stand reads as"
                       }.get(tone.persona, "your business health reads as")
            parts.append(f'{scope}, {subject} "{band}".')
        pillars = s.get("pillars", [])
        strong = [p for p in pillars if p.get("band") == "Strong"]
        if strong:
            parts.append(
                "Strongest: " + ", ".join(_pillar_label(p) for p in strong) + "."
            )
        # A red-flagged pillar is named in the prose itself. The rest of the
        # verdicts are not: the list below carries them (see below), but a red
        # flag is the one thing that must not depend on a reader scanning a
        # list, and test_unrelated_pillar_red_flag_does_not_trigger_section_h
        # pins that it surfaces here rather than only in a section that may not
        # render at all.
        flagged = [str(p.get("pillar_name")) for p in pillars
                   if p.get("red_flag_triggered") and p.get("pillar_name")]
        if flagged:
            parts.append(
                "Flagged for immediate attention: " + ", ".join(flagged) + "."
            )
        # The per-pillar verdicts are NOT prose. Each one is a name, a band and
        # a paragraph of description, and joining six of them with spaces
        # produced a single unreadable block that ran most of a page -- the
        # densest thing in the report and the least readable, which is backwards
        # for the section founders come for. The document renders them from
        # these same facts as a list (document._pillar_verdicts), so writing
        # them here too would print every verdict twice.
        return "\n\n".join(parts)

    def _problem_path(self, s, tone):
        intro = {"Validator": "What your answers point to: ",
                 "Auditor": "The diagnostic picture: ",
                 "Compass": "Here is the through-line: "}.get(tone.persona, "")
        lines = []
        for rc in s.get("root_causes", []):
            nm, status = rc.get("name"), rc.get("confirmation_status")
            if not nm:
                continue
            if status == "confirmed":
                lines.append(f"We confirmed {nm} through repeated probing -- a primary driver to act on.")
            elif status == "unconfirmed":
                lines.append(f"{nm} surfaced but eased when probed -- a secondary consideration, not a settled finding.")
            else:  # not_tested
                lines.append(f"{nm} is a possibility we did not directly test this session -- an area to explore, not a conclusion.")

        # Open by quoting the founder's own framing back to them, the way
        # every Page 3 in the Stage-Adaptive doc does. This template can only
        # set the two beside each other and let the founder feel the gap; it
        # deliberately does NOT assert a contradiction ("the real block isn't
        # X") the way the doc's examples do, because naming what the stated
        # symptom HIDES takes reading their actual probe answers. That is the
        # LLM narrator's job -- see the prompt guidance in the section spec.
        # Getting it wrong here would mean confidently telling a founder their
        # problem is not what they said it was, on template logic alone.
        stated = (s.get("stated_symptom") or "").strip()
        if stated:
            quoted = " ".join(stated.split())
            if len(quoted) > 300:  # keep the quote a quote, not a paragraph
                quoted = quoted[:297].rstrip() + "..."
            # Founders end the sentence themselves more often than not, and
            # closing the wrapper with its own full stop then renders as
            # `...know enough yet.".` -- so the outer stop is added only when
            # their own words did not already supply one.
            tail = "" if quoted.endswith((".", "!", "?")) else "."
            opener = f'You described the problem as "{quoted}"{tail}'
            if not lines:
                # No root cause to weigh it against -- record what they said
                # rather than returning nothing, so Page 3 still opens on
                # their words.
                return opener
            return f"{opener} {intro}{' '.join(lines)}"

        if not lines:
            return ""
        return intro + " ".join(lines)

    def _areas_to_monitor(self, s, tone):
        cats = list(s.get("categories") or [])  # names only -- never the raw score
        if not cats:
            return "No single critical issue stood out this session."
        return (
            "No single critical issue stood out. Rather than force a diagnosis, keep an "
            "eye on these areas as you go: " + ", ".join(cats) + "."
        )

    def _supporting_evidence(self, s, tone):
        parts = []
        probes = s.get("probes") or []
        answered = int(s.get("diagnosis_answers") or 0)
        if probes or answered:
            # BOTH halves of the evidence, because the report is built from
            # both. Naming only the symptom probes described a report written
            # from three questions when the founder had answered those three
            # AND the whole diagnosis -- which reads, correctly, as the
            # interview having been thrown away.
            bits = []
            if probes:
                bits.append(
                    f"{len(probes)} question{'s' if len(probes) != 1 else ''} "
                    "in your own words before the diagnosis started"
                )
            if answered:
                bits.append(
                    f"{answered} diagnosis answer{'s' if answered != 1 else ''}"
                )
            parts.append("This reads from " + " and ".join(bits) + ".")
        causes = s.get("root_causes") or []
        confirmed = [c["name"] for c in causes if c.get("confirmation_status") == "confirmed"]
        unconfirmed = [c["name"] for c in causes if c.get("confirmation_status") != "confirmed"]
        if confirmed:
            parts.append("Confirmed by your answers: " + ", ".join(confirmed) + ".")
        if unconfirmed:
            # Never let an untested cause read as settled -- the confirm actions
            # exist precisely to test these.
            parts.append(
                "Still to be tested: " + ", ".join(unconfirmed)
                + ". Treat these as the leading hypotheses, not verdicts."
            )
        return " ".join(parts)

    def _recommended_roadmap(self, s, tone):
        """Prose explains the SHAPE of the sequence; `facts` carries the ordered
        steps themselves.

        Deliberately emits no digits. An earlier cut numbered the lines
        ("1. Confirm: ...") and test_no_fabricated_numbers caught it: the report
        must never print a number that is not in the payload, and while an
        ordinal is formatting rather than a claim, the guard cannot tell the two
        apart -- and it is a guard worth more than a numbered list. The order is
        already structural in confirm_steps/solve_steps, which the client renders
        in sequence.
        """
        confirm = s.get("confirm_steps") or []
        solve = s.get("solve_steps") or []
        if confirm and solve:
            return (
                "Work this in two passes. First confirm what is actually true, "
                "then fix it -- the solve steps depend on what the confirm steps "
                "turn up, so running them out of order means solving for a "
                "problem you have not verified yet."
            )
        if confirm:
            return (
                "Start by confirming what is actually true. The fixes come after "
                "and depend on what you find, so there is nothing to sequence "
                "past this until these come back."
            )
        if solve:
            return "These are the moves, in the order they build on each other."
        return ""

    def _why_steps(self, s, tone):
        # Rationales come through as slots, not facts, precisely so they are
        # retold rather than pasted -- but the template narrator cannot rewrite,
        # only select. So it says what it can stand behind: which root causes
        # these steps address. The LLM narrator does the fuller job.
        causes = s.get("root_causes") or []
        if not causes:
            return ""
        lead = {"Auditor": "These steps target",
                "Validator": "These steps come from"}.get(tone.persona, "These steps are aimed at")
        return f"{lead} what the diagnosis pointed to: " + ", ".join(causes) + "."

    def _acknowledgement(self, s, tone):
        # Founder-facing copy that FOLLOWS the distress protocol -- it never quotes it.
        # tone.distress_protocol is a system directive and must not reach the founder.
        return (
            "Before we look at anything about the business: what you are carrying right "
            "now matters more than any diagnosis. There is no obligation to continue "
            "today -- you can stop here and come back when you have the capacity. How you "
            "are doing comes first."
        )

    def _support_recommendation(self, s, tone):
        return (
            "One first step, and it has nothing to do with the business: reach out to "
            "someone who can help with the weight of it -- a person you trust, or a "
            "professional -- not a business advisor. Give yourself permission to pause "
            "and pick this back up when you are ready."
        )

    def _hedge(self, s, tone):
        return (
            "One caveat up front: we did not gather enough signal this session to be "
            "confident. Read the below as a provisional draft, not a settled diagnosis."
        )

    def _priority_actions(self, s, tone):
        def steps(items):
            out = []
            for a in items:
                out.extend(a.get("next_actions", []))
            return [x for x in out if x]
        confirm = steps(s.get("confirm_actions", []))
        solve = steps(s.get("solve_actions", []))
        if not confirm and not solve:
            return ""
        lead = {"Auditor": "Recommended next steps.",
                "Validator": "Here is what to do next."}.get(tone.persona, "Your next steps.")
        out = [lead]
        if confirm:
            out.append("First, confirm: " + "; ".join(confirm) + ".")
        if solve:
            out.append(("Then start on: " if confirm else "Start on: ") + "; ".join(solve) + ".")
        return " ".join(out)

    def _discovery_cta(self, s, tone):
        # Fixed conversion CTA. Suppressed entirely under distress by the generator,
        # so it never reaches a founder in distress.
        return (
            "When you are ready to act on this, a short discovery call with the Ally "
            "team turns this diagnosis into a concrete plan. You can book one whenever "
            "the timing is right for you."
        )


class LLMSectionNarrator:
    """Per-section LLM narration. `llm` is any `str -> str` callable (a provider
    wrapper). Falls back to the template on empty/failed output, so it never
    blocks a report and never fabricates when the model misbehaves."""

    def __init__(self, llm: Callable[[str], str], *,
                 fallback: SectionNarrator | None = None,
                 long_llm: Callable[[str], str] | None = None):
        self.llm = llm
        # `summarise_dimensions` is the one call here that is not a section of
        # prose: it returns a JSON object covering every Founder-DNA dimension
        # the founder answered, a dozen or more, at one to two sentences each.
        # That does not fit in the section budget, and when it overruns the
        # reply is truncated mid-JSON, json.loads raises, the except swallows
        # it and EVERY card silently falls back to the raw answer -- which
        # _shorten then cuts to its first sentence. That is where "Core
        # Motivation: The bridge.", "Focus Attention: Last week." and
        # "Emotional Intelligence: Farhan." came from on live reports. The
        # prompt was never the problem; it never got to finish speaking.
        self.long_llm = long_llm or llm
        self.fallback = fallback or TemplateNarrator()

    def narrate(self, section_key: str, slots: dict[str, Any], tone: ToneGuidance) -> str:
        return self.narrate_with_source(section_key, slots, tone)[0]

    def summarise_dimensions(self, dimensions: dict[str, Any]) -> dict[str, str]:
        """Every Founder-DNA dimension compressed to a plain line or two.

        ONE call for all of them rather than one per dimension: a founder can
        answer a dozen dimensions, and a dozen round trips would cost more than
        the entire rest of report generation (0.4s of a 203s pipeline).

        Compression only. The model is given the founder's own answer and told
        to use nothing else, so a card can still only say what the founder said
        -- the same never-invent contract the section narration works under. Any
        dimension the model drops, mangles or returns as a non-string falls back
        to the deterministic trim, so a bad reply shortens the report rather
        than emptying it.
        """
        import json

        material = {k: t for k, v in dimensions.items() if (t := _answer_text(v))}
        if not material:
            return {}

        prompt = (
            "You are compressing a founder's own answers for their clarity report. "
            "Return ONLY a JSON object with exactly the same keys as the input.\n"
            "For each key, write 1-2 short sentences in plain, everyday English, "
            "addressed to the founder as \"you\".\n"
            # The cards print the summary UNDER a dimension label and nothing
            # else -- the question that produced the answer is not on the page.
            # So a summary that merely opens where the founder opened is
            # meaningless there. Live, two unrelated founders both got
            # "Core Motivation: The bridge", because the question offers a
            # choice between a trophy and a bridge and both answered "the
            # bridge"; the rest of what they said -- clinics that lose patients
            # to a notebook, a front desk getting home an hour earlier -- was
            # the actual content and was dropped. Other cards read "Decision
            # Style: I gather.", "Energy Patterns: March and April this year."
            "EACH SUMMARY MUST STAND ALONE. It is printed under a short label "
            "with no question next to it, so it has to make sense to someone "
            "who never saw the question. Never answer a question that is not "
            "shown: do not open with \"The bridge\", \"Yesterday\", \"March\", "
            "\"I gather\" or any other bare reply. Say the SUBSTANCE -- what "
            "they described, chose or care about, and why -- in a sentence that "
            "reads on its own.\n"
            "If the founder's answer opens with a short reply and then explains "
            "it, the explanation is the summary. Compress THAT.\n"
            "Use ONLY what that key's own text says. Never add a fact, name, number "
            "or judgement that is not already there, and never mix material between "
            "keys. If a value says too little to summarise, shorten it and leave the "
            "meaning alone.\n"
            "No quotes, no markdown, no preamble.\n"
            f"INPUT: {json.dumps(material, default=str)}"
        )
        try:
            parsed = json.loads(_json_object((self.long_llm(prompt) or "").strip()))
        except Exception:
            parsed = {}
        if not isinstance(parsed, dict):
            parsed = {}

        out: dict[str, str] = {}
        for key, original in material.items():
            summary = parsed.get(key)
            summary = " ".join(summary.split()) if isinstance(summary, str) else ""
            out[key] = _shorten(summary or original, _DIMENSION_SUMMARY_CHARS)
        return out

    @staticmethod
    def _has_narratable_content(slots: dict[str, Any]) -> bool:
        """Is there anything here for a model to write FROM?

        Booleans are excluded deliberately: a flag like `wellbeing_first`,
        `brief` or `cta` steers the SHAPE of a section, it is not material to
        write about. A section whose slots are only flags (or empty) has no
        content, and asking a model to write it under a strict never-invent
        instruction leaves it two options -- refuse, or fabricate.
        """
        for value in slots.values():
            if isinstance(value, bool):
                continue
            if isinstance(value, (int, float)):
                return True          # 0 is a value, not an absence
            if value:
                return True
        return False

    def narrate_with_source(self, section_key, slots, tone) -> tuple[str, str]:
        """Return (prose, source). A silent fallback would hide degraded quality,
        so the source distinguishes real LLM output ('llm') from a template
        fallback after an error/empty output ('llm_fallback_template')."""
        import json

        # Contentless sections never reach the model. `acknowledgement` and
        # `support_recommendation` carry no slots at all -- they are fixed,
        # carefully-worded copy that the template narrator already holds -- and
        # sending them anyway produced exactly the refusal the instructions ask
        # for: a live distress report opened with "I don't have enough
        # information to write this section -- no facts were provided to draw
        # from," twice, as the first two things a founder in distress read.
        #
        # `out` was non-empty, so the fallback below never fired. The fix is not
        # to sniff the model's wording for a refusal -- that is brittle and
        # locale-dependent -- but to stop asking a question that has no answer.
        if not self._has_narratable_content(slots):
            return self.fallback.narrate(section_key, slots, tone), "template_no_slots"

        directives = [
            "You are writing ONE section of a founder's clarity report. Write 1-3 warm, "
            "plain sentences. Persona: " + (tone.persona or "neutral") + ".",
            "Use ONLY the facts in the JSON below. Never invent or change a number, name, "
            "score or claim. If a value is missing, do not mention it or the topic it "
            "would have covered -- do not guess, infer, or fill the gap with a plausible-"
            "sounding statement.",
        ]
        if slots.get("brief"):
            # Business content is deliberately de-prioritised under distress (the
            # founder's wellbeing comes first) -- the LLM must match the template's
            # single-sentence behaviour here, not write a full paragraph with a
            # pillar breakdown.
            directives.append(
                "IMPORTANT: this section must be BRIEF -- exactly ONE short sentence "
                "naming only the overall band, plus one line saying more detail can "
                "wait. Do NOT list individual pillars, bands, or descriptions."
            )
        if section_key == "founder_dna":
            # This section's slots are the founder's raw answers, and quoting
            # them was producing a page-long opening paragraph that repeated,
            # verbatim, the same vision text rendered in the card right below
            # it. The founder learns nothing from re-reading what they typed;
            # what they came for is what it ADDS UP TO.
            directives.append(
                "Write at most 3 short sentences of plain, everyday English "
                "naming the pattern these answers share -- how this founder "
                "operates. Do NOT quote or paraphrase any answer at length, and "
                "do not walk through the dimensions one by one; each is already "
                "shown beside this paragraph, so repeating one wastes the only "
                "place that can say what they mean together. A quoted fragment, "
                "if it genuinely earns its place, must be under 12 words."
            )
        if section_key == "problem_path" and slots.get("stated_symptom"):
            # The one section with a prescribed shape. Every Page 3 in the
            # Stage-Adaptive doc makes the same three moves, and the third --
            # naming what the stated symptom HIDES -- is the entire reason a
            # founder feels decoded rather than surveyed. The template
            # narrator cannot do it (it would be asserting a contradiction it
            # never read the evidence for), so it is specified here.
            #
            # The guard rails matter more than the shape: this is the only
            # place the report tells a founder they are wrong about their own
            # business, so the contradiction is allowed ONLY where their own
            # probe answers carry it. With no such evidence the model is told
            # to stop after two moves rather than reach for a plausible third.
            directives.append(
                "This section follows a FIXED three-move shape:\n"
                "1. Quote the founder's own framing back to them, using "
                "stated_symptom close to verbatim (trim for length, never "
                "reword their meaning).\n"
                "2. Set their own evidence beside it, drawn ONLY from "
                "symptom_probes -- reference what they actually said.\n"
                "3. Name the gap between the two, in the shape 'the real "
                "block isn't <what they said> -- it's <the root cause in "
                "root_causes>'.\n"
                "Move 3 is permitted ONLY when a specific answer in "
                "symptom_probes genuinely conflicts with stated_symptom. If "
                "nothing in symptom_probes supports the contradiction, or "
                "root_causes is empty, write moves 1 and 2 and STOP -- never "
                "manufacture a contradiction to complete the pattern. A root "
                "cause whose confirmation_status is not 'confirmed' must be "
                "worded as a possibility, not a verdict. Up to 4 sentences "
                "for this section."
            )
        prompt = (
            "\n".join(directives)
            + f"\nSECTION: {section_key}\nFACTS: {json.dumps(slots, default=str)}"
        )
        try:
            out = (self.llm(prompt) or "").strip()
        except Exception:
            out = ""
        if out:
            return out, "llm"
        return self.fallback.narrate(section_key, slots, tone), "llm_fallback_template"
