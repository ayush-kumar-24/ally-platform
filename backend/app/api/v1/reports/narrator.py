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

from dataclasses import dataclass
from typing import Any, Callable, Protocol


@dataclass(frozen=True)
class ToneGuidance:
    persona: str | None                 # Validator / Compass / Auditor
    tone_prompt: str | None = None      # prompt_library stage tone text (LLM only)
    session_framing: str | None = None  # session_state_bands.report_framing_adjustment
    distress_protocol: str | None = None  # prompt_library distress protocol text


class SectionNarrator(Protocol):
    def narrate(self, section_key: str, slots: dict[str, Any], tone: ToneGuidance) -> str: ...


class TemplateNarrator:
    """Deterministic prose from slots only. Every number it emits comes verbatim
    from a slot value; it never computes or invents."""

    def narrate(self, section_key: str, slots: dict[str, Any], tone: ToneGuidance) -> str:
        fn = getattr(self, f"_{section_key}", None)
        return fn(slots, tone) if fn else ""

    def narrate_with_source(self, section_key, slots, tone) -> tuple[str, str]:
        return self.narrate(section_key, slots, tone), "template"

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
            parts.append(f'In your own words, this is what success looks like: "{vision}"')
        blind_spots = s.get("strengths_blind_spots")
        if blind_spots:
            parts.append("A pattern worth naming: " + blind_spots[0])
        # purpose_mission gets the same one-line treatment as vision (both are
        # "why this matters" statements); the other 5 phase-2 dimensions stay
        # card-only here, same as origin/stress_response/communication_
        # preference above -- narrating all 9+ possible dimensions in prose
        # would be exactly the wall-of-text this fallback is written to avoid.
        purpose_mission = s.get("purpose_mission")
        if purpose_mission:
            parts.append(f'On why this matters to you: "{purpose_mission[0]}"')
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
            lead = {"Auditor": "Across the six readiness pillars, business health reads as",
                    "Validator": "Across the six readiness pillars, where you stand reads as"
                    }.get(tone.persona, "Across the six readiness pillars, your business health reads as")
            parts.append(f'{lead} "{band}".')
        pillars = s.get("pillars", [])
        strong = [p for p in pillars if p.get("band") == "Strong"]
        if strong:
            parts.append("Strongest: " + ", ".join(p["pillar_name"] for p in strong) + ".")
        concern = [p for p in pillars if p.get("band") in ("Critical Gap", "Needs Attention")]
        for p in concern:
            desc = p.get("band_description")
            line = f"{p['pillar_name']} — {p.get('band')}."
            if desc:
                line += f" {desc}"
            parts.append(line)
        return " ".join(parts)

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

    def __init__(self, llm: Callable[[str], str], *, fallback: SectionNarrator | None = None):
        self.llm = llm
        self.fallback = fallback or TemplateNarrator()

    def narrate(self, section_key: str, slots: dict[str, Any], tone: ToneGuidance) -> str:
        return self.narrate_with_source(section_key, slots, tone)[0]

    def narrate_with_source(self, section_key, slots, tone) -> tuple[str, str]:
        """Return (prose, source). A silent fallback would hide degraded quality,
        so the source distinguishes real LLM output ('llm') from a template
        fallback after an error/empty output ('llm_fallback_template')."""
        import json

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
