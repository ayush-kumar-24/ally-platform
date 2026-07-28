"""Ally Prompt Grounding (Phase 5, Milestone 2.1) -- additive over frozen M2.

Extends prompt construction so a prompt can be grounded in the founder's context
(M1), memory (M6), retrieved knowledge (M3) and knowledge-graph expansion (M4) plus
their message -- without editing any frozen M2 template or subsystem. The
GroundedPromptManager subclasses the frozen PromptManager and adds render_grounded;
the orchestrator only hands it a PipelineContext-shaped GroundingSource.
"""

from app.api.v1.ally.prompts.grounding.errors import GroundingError
from app.api.v1.ally.prompts.grounding.flatteners import (
    graph_expansion,
    memory_summary,
    retrieved_knowledge,
)
from app.api.v1.ally.prompts.grounding.grounded_variables import grounded_variables
from app.api.v1.ally.prompts.grounding.library import (
    CATEGORY_DIAGNOSIS_ANSWER_GROUNDED,
    GROUNDED_TEMPLATES,
    default_grounded_prompt_manager,
    grounded_prompt_repository,
)
from app.api.v1.ally.prompts.grounding.manager import GroundedPromptManager
from app.api.v1.ally.prompts.grounding.source import GroundingSource, RequestLike

__all__ = [
    "GroundedPromptManager",
    "GroundingSource",
    "RequestLike",
    "GroundingError",
    "grounded_variables",
    "memory_summary",
    "retrieved_knowledge",
    "graph_expansion",
    "default_grounded_prompt_manager",
    "grounded_prompt_repository",
    "GROUNDED_TEMPLATES",
    "CATEGORY_DIAGNOSIS_ANSWER_GROUNDED",
]
