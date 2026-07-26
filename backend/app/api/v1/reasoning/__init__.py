"""Reasoning layer (Tier-1 Core Reasoning Systems).

Public surface: the orchestrator, its DI factory, the configuration entry point,
and the result DTO. Engine algorithms are implemented incrementally in their own
approved steps behind the interfaces in `interfaces.py`.
"""

from app.api.v1.reasoning.config import ReasoningConfig, build_reasoning_config
from app.api.v1.reasoning.deps import get_reasoning_service
from app.api.v1.reasoning.schemas import ReasoningResult
from app.api.v1.reasoning.service import ReasoningService

__all__ = [
    "ReasoningConfig",
    "ReasoningResult",
    "ReasoningService",
    "build_reasoning_config",
    "get_reasoning_service",
]
