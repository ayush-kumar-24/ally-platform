"""Ally Context Builder (Phase 5, Milestone 1).

The read-model that assembles a typed, immutable AllyContext from the frozen
diagnosis outputs. It is the grounding object every other Phase-5 component
consumes and the enforcement point for "never ignore diagnosis context".
"""

from app.api.v1.ally.context.builder import AllyContextBuilder, build_ally_context
from app.api.v1.ally.context.errors import AllyContextError, FounderNotFoundError
from app.api.v1.ally.context.repository import AllyContextRepository
from app.api.v1.ally.context.schemas import (
    ALLY_CONTEXT_SCHEMA_VERSION,
    AllyContext,
    BusinessHealthContext,
    DiagnosisContext,
    FounderProfileContext,
    InternalIntelligenceContext,
    RootCauseContext,
)

__all__ = [
    "AllyContextBuilder",
    "build_ally_context",
    "AllyContextRepository",
    "AllyContextError",
    "FounderNotFoundError",
    "ALLY_CONTEXT_SCHEMA_VERSION",
    "AllyContext",
    "FounderProfileContext",
    "DiagnosisContext",
    "RootCauseContext",
    "BusinessHealthContext",
    "InternalIntelligenceContext",
]
