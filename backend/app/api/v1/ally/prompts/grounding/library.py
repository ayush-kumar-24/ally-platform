"""Grounded prompt library (M2.1) -- new template VERSIONS, added as data.

These are the grounded successors of the M2 v1 diagnosis-answer templates. They live
under a distinct category (`diagnosis_answer_grounded`) and carry version=2, so:
  * the frozen default repository/manager still resolve the original v1 templates
    unchanged, and
  * the grounded repository additionally carries these v2 templates for the
    GroundedPromptManager.

The grounded repository = frozen BUILTIN_TEMPLATES (imported, unmodified) + these.
No frozen file is edited; adding a grounded template is pure data, as in M2.
"""

from __future__ import annotations

from app.api.v1.ally.prompts.grounding.manager import GroundedPromptManager
from app.api.v1.ally.prompts.library import BUILTIN_TEMPLATES, CATEGORY_DIAGNOSIS_ANSWER
from app.api.v1.ally.prompts.repository import InMemoryPromptRepository, PromptRepository
from app.api.v1.ally.prompts.schemas import PromptMetadata, PromptTemplate

CATEGORY_DIAGNOSIS_ANSWER_GROUNDED = CATEGORY_DIAGNOSIS_ANSWER + "_grounded"

_GROUNDED_SYSTEM = (
    "You are Ally, a diagnostic co-pilot for startup founders. You answer using ONLY "
    "the grounded sections provided below -- the founder's diagnosis, their stored "
    "memory, the retrieved knowledge and the related diagnostic map. You never invent "
    "findings, scores, sources or advice absent from these sections. Retrieved "
    "knowledge and the diagnostic map are SUPPORT for the diagnosis; if any source "
    "conflicts with the diagnosis, defer to the diagnosis. If the sections do not "
    "contain the answer, say so plainly rather than guessing."
)

_GROUNDED_STANDARD_V2 = PromptTemplate(
    template_key="diagnosis_answer_grounded.standard",
    version=2,
    category=CATEGORY_DIAGNOSIS_ANSWER_GROUNDED,
    distress_mode=False,
    language="en",
    system_prompt=_GROUNDED_SYSTEM,
    user_prompt=(
        "Founder: {{founder_name}} (stage: {{stage_name}}).\n"
        "Diagnostic confidence: {{overall_confidence}}/100.\n\n"
        "== Diagnosis summary ==\n{{executive_summary}}\n\n"
        "== Top root causes ==\n{{top_root_causes}}\n\n"
        "== Founder memory (prior context) ==\n{{memory_summary}}\n\n"
        "== Retrieved knowledge (support) ==\n{{retrieved_knowledge}}\n\n"
        "== Related diagnostic map (support) ==\n{{graph_expansion}}\n\n"
        "== Founder's message ==\n{{founder_message}}\n\n"
        "Answer the founder's message grounded strictly in the sections above. "
        "Reference root causes by name where relevant, use the retrieved knowledge and "
        "diagnostic map only to support the diagnosis, and never contradict it or "
        "introduce facts that are not present above."
    ),
    required_variables=(
        "founder_name",
        "stage_name",
        "overall_confidence",
        "executive_summary",
        "top_root_causes",
        "memory_summary",
        "retrieved_knowledge",
        "graph_expansion",
        "founder_message",
    ),
    metadata=PromptMetadata(
        author="ally-core",
        description="Grounded answer: diagnosis + memory + retrieval + graph + message.",
        tags=("diagnosis", "answer", "grounded"),
    ),
)

_GROUNDED_DISTRESS_V2 = PromptTemplate(
    template_key="diagnosis_answer_grounded.distress",
    version=2,
    category=CATEGORY_DIAGNOSIS_ANSWER_GROUNDED,
    distress_mode=True,
    language="en",
    system_prompt=(
        _GROUNDED_SYSTEM
        + " Wellbeing comes before diagnostics: the founder is showing signs of "
        "distress. Lead with warmth and support, do NOT surface scores, retrieved "
        "knowledge or a clinical breakdown, and gently offer to continue when ready."
    ),
    user_prompt=(
        "Founder: {{founder_name}}.\n\n"
        "== What we remember about them (for warmth, not analysis) ==\n"
        "{{memory_summary}}\n\n"
        "== Founder's message ==\n{{founder_message}}\n\n"
        "Respond with genuine empathy first. Acknowledge how they feel, remind them "
        "they are not alone, and only offer next steps if they signal they want them. "
        "Do not present diagnostic scores or retrieved analysis."
    ),
    required_variables=("founder_name", "founder_message", "memory_summary"),
    metadata=PromptMetadata(
        author="ally-core",
        description="Wellbeing-first grounded response when the context flags distress.",
        tags=("distress", "wellbeing", "grounded"),
    ),
)

GROUNDED_TEMPLATES: tuple[PromptTemplate, ...] = (
    _GROUNDED_STANDARD_V2,
    _GROUNDED_DISTRESS_V2,
)


def grounded_prompt_repository() -> PromptRepository:
    """Frozen originals (still resolvable) + the grounded v2 templates."""
    return InMemoryPromptRepository(BUILTIN_TEMPLATES + GROUNDED_TEMPLATES)


def default_grounded_prompt_manager() -> GroundedPromptManager:
    return GroundedPromptManager(grounded_prompt_repository())
