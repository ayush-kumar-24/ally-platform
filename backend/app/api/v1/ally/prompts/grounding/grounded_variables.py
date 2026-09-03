"""Assemble the full grounded variable dict for interpolation.

Base variables come from the frozen M1->prompt flattener (context_variables), which
fails closed by OMITTING absent values. On top of that we add the four grounding
blocks + the founder message.

Grounding blocks are ALWAYS populated: when a source is empty we substitute an
explicit absence sentinel (e.g. "No stored founder memory yet.") rather than
omitting the key. This is deliberate -- the grounded templates reference these
placeholders unconditionally, and stating an absence is accurate, not fabricated.
The founder message is added only when present, so a blank message fails closed as a
missing required variable.
"""

from __future__ import annotations

from app.api.v1.ally.prompts.context_variables import context_variables
from app.api.v1.ally.prompts.grounding.flatteners import (
    attachments_block as _attachments_block,
    diagnosis_block as _diagnosis_block,
    graph_expansion,
    memory_summary,
    retrieved_knowledge,
)
from app.api.v1.ally.prompts.grounding.source import GroundingSource

_MEMORY_NONE = "No stored founder memory yet."
_RETRIEVAL_NONE = "No supporting knowledge retrieved."
_GRAPH_NONE = "No related diagnostic map available."
_DIAGNOSIS_NONE = "No diagnosis completed yet."
_ATTACHMENTS_NONE = "No files uploaded in this conversation."
_TASKS_NONE = "No active tasks on the founder's plan."
#: Said plainly so the model does not invent a profile to fill the gap -- and
#: so it can tell the founder to complete onboarding rather than denying the
#: data exists.
_PROFILE_NONE = "Onboarding profile not completed."
_FOUNDER_NAME_FALLBACK = "the founder"
_STAGE_NAME_FALLBACK = "not set yet"


def grounded_variables(source: GroundingSource) -> dict[str, str]:
    ctx = source.ally_context
    variables = context_variables(ctx)  # base M1 vars (fail-closed omission)
    variables.setdefault("founder_name", _FOUNDER_NAME_FALLBACK)
    variables.setdefault("stage_name", _STAGE_NAME_FALLBACK)

    message = (source.request.message or "").strip()
    if message:
        variables["founder_message"] = message

    variables["memory_summary"] = memory_summary(source.memory_items) or _MEMORY_NONE
    variables["retrieved_knowledge"] = retrieved_knowledge(source.retrieval) or _RETRIEVAL_NONE
    variables["graph_expansion"] = graph_expansion(source.graph) or _GRAPH_NONE
    variables["diagnosis_block"] = _diagnosis_block(ctx) or _DIAGNOSIS_NONE
    # Only ConversationContextWindow (the ai_chat GroundingSource) carries
    # attachments; other GroundingSource implementers (tests, the orchestrator's
    # PipelineContext) simply have none -- getattr keeps this additive/optional.
    variables["attachments_block"] = getattr(source, "attachments_text", "") or _ATTACHMENTS_NONE
    # Same optional/additive convention as attachments_text -- only the ai_chat
    # GroundingSource carries tasks_text.
    variables["tasks_block"] = getattr(source, "tasks_text", "") or _TASKS_NONE
    # Same optional/additive convention again. This one is what onboarding
    # collected -- stage, industry, revenue, what they are building, the problem
    # they arrived with -- which chat never had, so Ally denied having details
    # the founder had already given it.
    variables["founder_profile_block"] = (
        getattr(source, "profile_text", "") or _PROFILE_NONE
    )
    return variables
