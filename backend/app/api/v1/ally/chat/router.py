"""Ally chat endpoint -- the HTTP adapter for the AgentOrchestrator (M7).

Serialisation, auth and HTTP mapping only. No business rules: the orchestrator
runs the pipeline and is itself fail-closed, so this layer just translates the
OrchestratorResponse into an HTTP response, logs with the request_id, and never
leaks stack traces or internal error strings.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status

# Phase 3's get_founder_record resolves the AuthUser token -> Founders row.
from app.api.deps import get_founder_record as get_current_founder
from app.api.v1.ally.chat.deps import get_orchestrator_service
from app.api.v1.ally.chat.schemas import ChatMetrics, ChatRequest, ChatResponse, ChatTrace
from app.api.v1.ally.orchestrator import FounderRequest, OrchestratorResponse, OrchestratorService
from app.core.logger import logger
from app.middleware.error_handler import AppError
from app.models import Founder

router = APIRouter(prefix="/ally", tags=["ally"])

# Founder-safe messages by failing step -> never expose internals; details go to logs.
_USER_MESSAGE = {
    "build_context": "No diagnosis is available for you yet. Complete an assessment first.",
    "build_prompt": "The assistant is temporarily unavailable. Please try again later.",
    "execute_ai": "The assistant is temporarily unavailable. Please try again.",
}
_STATUS = {
    "build_context": status.HTTP_404_NOT_FOUND,
    "build_prompt": status.HTTP_500_INTERNAL_SERVER_ERROR,
    "execute_ai": status.HTTP_503_SERVICE_UNAVAILABLE,
}


@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="Ask Ally (the AI agent) a question, grounded in your diagnosis",
)
def chat(
    payload: ChatRequest,
    response: Response,
    founder: Founder = Depends(get_current_founder),
    service: OrchestratorService = Depends(get_orchestrator_service),
) -> ChatResponse:
    request_id = payload.request_id or str(uuid.uuid4())

    # Security: the founder is the authenticated identity. A body founder_id is
    # accepted only if it matches -- it can never select another founder's data.
    if payload.founder_id is not None and payload.founder_id != founder.founder_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="founder_id does not match the authenticated founder.",
        )

    logger.info(
        "ally.chat request",
        extra={"request_id": request_id, "founder_id": founder.founder_id,
               "message_length": len(payload.message)},
    )

    founder_request = FounderRequest(
        founder_id=founder.founder_id, message=payload.message, session_id=payload.session_id,
        request_id=request_id, language=payload.language, response_category=payload.response_category,
    )

    try:
        result = service.handle(founder_request)
    except AppError:
        raise  # rendered by the global handler (status + message, no stack trace)
    except Exception:
        logger.exception("ally.chat unexpected error", extra={"request_id": request_id})
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred while processing your request.",
        )

    logger.info(
        "ally.chat response",
        extra={"request_id": request_id, "ok": result.ok, "failed_step": result.trace.failed_step,
               "duration_ms": result.trace.duration_ms, "provider": result.trace.provider,
               "model": result.trace.model, "total_tokens": result.trace.metrics.token_usage.total_tokens,
               "error": result.error},
    )

    response.status_code = _STATUS.get(result.trace.failed_step or "", status.HTTP_200_OK)
    return _to_response(result)


def _to_response(result: OrchestratorResponse) -> ChatResponse:
    m = result.trace.metrics
    friendly_error = None if result.ok else _USER_MESSAGE.get(
        result.trace.failed_step or "", "The request could not be completed."
    )
    return ChatResponse(
        request_id=result.request_id,
        ok=result.ok,
        answer=result.answer,
        response_type=result.response_type,
        confidence=float(result.confidence) if result.confidence is not None else None,
        citations=list(result.citations),
        error=friendly_error,
        trace=ChatTrace(
            request_id=result.trace.request_id,
            duration_ms=result.trace.duration_ms,
            completed_steps=list(result.trace.completed_steps),
            failed_step=result.trace.failed_step,
            provider=result.trace.provider,
            model=result.trace.model,
            metrics=ChatMetrics(
                memory_reads=m.memory_reads, retrieval_hits=m.retrieval_hits,
                graph_nodes=m.graph_nodes, prompt_version=m.prompt_version,
                total_tokens=m.token_usage.total_tokens,
            ),
        ),
    )
