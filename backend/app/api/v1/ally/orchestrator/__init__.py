"""Ally Agent Orchestration Layer (Phase 5, Milestone 7) -- the composition root.

The ONLY layer that imports and composes M1-M6. It coordinates the fixed 9-step
pipeline (context -> memory -> retrieval -> graph -> prompt -> execute -> persist)
through each subsystem's public interface, fails closed per step, and returns a
fully-traced OrchestratorResponse. It contains no business logic and duplicates
none -- only composition.
"""

from app.api.v1.ally.orchestrator.executor import (
    OrchestratorConfig,
    PipelineExecutor,
)
from app.api.v1.ally.orchestrator.orchestrator import (
    AgentOrchestrator,
    OrchestratorService,
    build_offline_orchestrator,
)
from app.api.v1.ally.orchestrator.schemas import (
    FounderRequest,
    OrchestratorResponse,
    PipelineContext,
    PipelineMetrics,
    PipelineTrace,
)

__all__ = [
    "AgentOrchestrator",
    "OrchestratorService",
    "build_offline_orchestrator",
    "PipelineExecutor",
    "OrchestratorConfig",
    "FounderRequest",
    "OrchestratorResponse",
    "PipelineContext",
    "PipelineMetrics",
    "PipelineTrace",
]
