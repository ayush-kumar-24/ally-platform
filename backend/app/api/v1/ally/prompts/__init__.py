"""Ally Prompt layer (Phase 5, Milestone 2).

Deterministic prompt preparation from the immutable AllyContext. The Prompt
Manager consumes ONLY AllyContext (via the context flattener) and a
PromptRepository -- never the database, an LLM, RAG, memory, the router or the
knowledge graph. It returns a typed RenderedPrompt, never a raw string.
"""

from app.api.v1.ally.prompts.context_variables import context_variables
from app.api.v1.ally.prompts.errors import (
    MissingPromptVariableError,
    PromptError,
    PromptNotFoundError,
    RenderingError,
    TemplateVersionError,
    UnsupportedLanguageError,
)
from app.api.v1.ally.prompts.library import (
    BUILTIN_TEMPLATES,
    CATEGORY_DIAGNOSIS_ANSWER,
    default_prompt_manager,
    default_prompt_repository,
)
from app.api.v1.ally.prompts.manager import PromptManager
from app.api.v1.ally.prompts.repository import InMemoryPromptRepository, PromptRepository
from app.api.v1.ally.prompts.schemas import (
    PromptMetadata,
    PromptSelection,
    PromptTemplate,
    RenderedPrompt,
)

__all__ = [
    "PromptManager",
    "PromptRepository",
    "InMemoryPromptRepository",
    "PromptTemplate",
    "RenderedPrompt",
    "PromptMetadata",
    "PromptSelection",
    "context_variables",
    "default_prompt_manager",
    "default_prompt_repository",
    "BUILTIN_TEMPLATES",
    "CATEGORY_DIAGNOSIS_ANSWER",
    "PromptError",
    "PromptNotFoundError",
    "TemplateVersionError",
    "MissingPromptVariableError",
    "UnsupportedLanguageError",
    "RenderingError",
]
