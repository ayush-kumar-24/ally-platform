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
        arch = s.get("archetype")
        if not arch or not arch.get("name"):
            return ""
        name, motiv = arch["name"], arch.get("core_motivation")
        motiv_txt = f", driven by {motiv.lower()}" if motiv else ""
        if arch.get("is_confident"):
            return f"Your founder pattern reads clearly as the {name}{motiv_txt}."
        return (
            f"Your answers lean toward the {name} pattern{motiv_txt}, but the signal is "
            "mixed -- treat this as a starting hypothesis to test, not a fixed label."
        )

    def _psychological_note(self, s, tone):
        # Section H content is the Critical Gap band description; fall back to the
        # red-flag note / session framing only if that is absent.
        body = s.get("section_h_text") or s.get("red_flag_note") or tone.session_framing
        if not body:
            return ""
        base = "A note on where you are right now, before anything about the business. "
        sep = s.get("separate_identity")
        sep_txt = " The business has challenges. You are not those challenges." if sep else ""
        return base + body + sep_txt

    def _business_dna(self, s, tone):
        # Bands + written descriptions -- never raw numbers.
        parts = []
        band = s.get("overall_band")
        if band:
            parts.append(f'Across the six readiness pillars, your business health reads as "{band}".')
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
        return " ".join(lines)

    def _areas_to_monitor(self, s, tone):
        cats = [c for c, _ in s.get("categories", [])]
        if not cats:
            return "No single critical issue stood out this session."
        return (
            "No single critical issue stood out. Rather than force a diagnosis, keep an "
            "eye on these areas as you go: " + ", ".join(cats) + "."
        )

    def _acknowledgement(self, s, tone):
        ack = tone.distress_protocol or s.get("framing") or (
            "This sounds like a genuinely hard stretch."
        )
        # Keep only the first sentence of the protocol text as the acknowledgement.
        first = ack.split(". ")[0].strip().rstrip(".")
        return f"{first}. Before anything about the business -- how you are doing comes first."

    def _support_recommendation(self, s, tone):
        return (
            "A first step that has nothing to do with the business: reconnect with one "
            "person you trust, and give yourself permission to pause the diagnostic and "
            "come back to it when you have capacity."
        )

    def _hedge(self, s, tone):
        return (
            "One caveat up front: we did not gather enough signal this session to be "
            "confident. Read the below as a provisional draft, not a settled diagnosis."
        )

    def _priority_actions(self, s, tone):
        n = len(s.get("confirm_actions", [])) + len(s.get("solve_actions", []))
        if not n:
            return ""
        return "Your next steps, grouped into what to confirm first and what to start solving:"


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

        prompt = (
            "You are writing ONE section of a founder's clarity report. Write 1-3 warm, "
            "plain sentences. Persona: " + (tone.persona or "neutral") + ". "
            "Use ONLY the facts in the JSON below. Never invent or change a number, name, "
            "score or claim. If a value is missing, do not mention it.\n"
            f"SECTION: {section_key}\nFACTS: {json.dumps(slots, default=str)}"
        )
        try:
            out = (self.llm(prompt) or "").strip()
        except Exception:
            out = ""
        if out:
            return out, "llm"
        return self.fallback.narrate(section_key, slots, tone), "llm_fallback_template"
