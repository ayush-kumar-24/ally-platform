"""Built-in Ally prompt library + default wiring.

Templates are DATA, not code paths -- adding one here (or, later, a
DbPromptRepository row) does not change the Manager. This module also exposes the
default repository/manager factories the orchestrator (a later milestone) will use.

`CATEGORY_DIAGNOSIS_ANSWER` carries two templates that differ only by
`distress_mode`, so the Manager selects the wellbeing-first variant automatically
when the context is distressed.
"""

from __future__ import annotations

from app.api.v1.ally.prompts.manager import PromptManager
from app.api.v1.ally.prompts.repository import InMemoryPromptRepository, PromptRepository
from app.api.v1.ally.prompts.schemas import PromptMetadata, PromptTemplate

CATEGORY_DIAGNOSIS_ANSWER = "diagnosis_answer"

_SYSTEM = (
    "You are Ally, a diagnostic co-pilot for startup founders. You answer ONLY from "
    "the founder's diagnosis context provided below; you never invent findings, "
    "scores, or advice that the diagnosis does not support. If the context does not "
    "contain the answer, say so plainly."
)

_DIAGNOSIS_ANSWER_V1 = PromptTemplate(
    template_key="diagnosis_answer.standard",
    version=1,
    category=CATEGORY_DIAGNOSIS_ANSWER,
    distress_mode=False,
    language="en",
    system_prompt=_SYSTEM,
    user_prompt=(
        "Founder: {{founder_name}} (stage: {{stage_name}}).\n"
        "Diagnostic confidence: {{overall_confidence}}/100.\n\n"
        "Diagnosis summary:\n{{executive_summary}}\n\n"
        "Top root causes:\n{{top_root_causes}}\n\n"
        "Answer the founder's question grounded strictly in the above. Reference the "
        "root causes by name where relevant, and never contradict the diagnosis."
    ),
    required_variables=(
        "founder_name",
        "stage_name",
        "overall_confidence",
        "executive_summary",
        "top_root_causes",
    ),
    metadata=PromptMetadata(
        author="ally-core",
        description="Standard grounded answer for a founder with a completed diagnosis.",
        tags=("diagnosis", "answer"),
    ),
)

_DIAGNOSIS_ANSWER_DISTRESS_V1 = PromptTemplate(
    template_key="diagnosis_answer.distress",
    version=1,
    category=CATEGORY_DIAGNOSIS_ANSWER,
    distress_mode=True,
    language="en",
    system_prompt=(
        _SYSTEM
        + " Wellbeing comes before diagnostics: the founder is showing signs of "
        "distress. Lead with warmth and support, do NOT surface scores or a "
        "clinical breakdown, and gently offer to continue when they are ready."
    ),
    user_prompt=(
        "Founder: {{founder_name}}.\n\n"
        "This founder is in a hard moment. Respond with genuine empathy first. "
        "Acknowledge how they feel, remind them they are not alone, and only offer "
        "next steps if they signal they want them. Do not present diagnostic scores."
    ),
    required_variables=("founder_name",),
    metadata=PromptMetadata(
        author="ally-core",
        description="Wellbeing-first response when the diagnosis flags distress.",
        tags=("distress", "wellbeing"),
    ),
)

BUILTIN_TEMPLATES: tuple[PromptTemplate, ...] = (
    _DIAGNOSIS_ANSWER_V1,
    _DIAGNOSIS_ANSWER_DISTRESS_V1,
)


def default_prompt_repository() -> PromptRepository:
    """The built-in library as a repository. Swap for a DB-backed repository later
    without changing the Manager."""
    return InMemoryPromptRepository(BUILTIN_TEMPLATES)


def default_prompt_manager() -> PromptManager:
    return PromptManager(default_prompt_repository())
