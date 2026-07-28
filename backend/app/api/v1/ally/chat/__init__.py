"""HTTP adapter for the Ally AgentOrchestrator (Phase 5 integration).

The FastAPI layer over the frozen AI foundation: it exposes POST /api/v1/ally/chat
using only the orchestrator's public interface, and modifies no AI subsystem.
"""

from app.api.v1.ally.chat.router import router

__all__ = ["router"]
