"""PipelineExecutor -- runs the fixed 9-step pipeline by calling each subsystem.

This is where the calls happen; it holds NO business logic of its own -- it only
sequences the subsystems through their public interfaces and records a trace.

Fail-closed per the contract:
  * Memory / Retrieval / Graph failure  -> log and CONTINUE (that step is skipped;
    its metric stays 0; nothing is fabricated).
  * Context or Prompt failure -> nothing can be sent to the model, so it returns a
    failed OrchestratorResponse (ok=False) with the failing step named.
  * AI failure -> failed OrchestratorResponse (ok=False), empty answer.

Deterministic given the same inputs, subsystems and injected clock.
"""

from __future__ import annotations

from datetime import datetime

from app.api.v1.ally.execution.schemas import AIRequest, TokenUsage
from app.api.v1.ally.memory.clock import Clock, SystemClock
from app.api.v1.ally.memory.schemas import MemorySearchRequest, MemoryType
from app.api.v1.ally.orchestrator.schemas import (
    FounderRequest,
    OrchestratorResponse,
    PipelineContext,
    PipelineMetrics,
    PipelineTrace,
)
from app.core.logger import logger

# Step names (also the values recorded in the trace's completed_steps).
BUILD_CONTEXT = "build_context"
RETRIEVE_MEMORY = "retrieve_memory"
RETRIEVE_KNOWLEDGE = "retrieve_knowledge"
EXPAND_GRAPH = "expand_graph"
BUILD_PROMPT = "build_prompt"
EXECUTE_AI = "execute_ai"
PERSIST_MEMORY = "persist_memory"


class OrchestratorConfig:
    def __init__(
        self,
        *,
        memory_search_limit: int = 5,
        persist_importance: int = 50,
        persist_memory_type: MemoryType = MemoryType.WORKING,
    ):
        self.memory_search_limit = memory_search_limit
        self.persist_importance = persist_importance
        self.persist_memory_type = persist_memory_type


class PipelineExecutor:
    def __init__(
        self,
        *,
        context_builder,
        memory,
        retrieval,
        knowledge_graph,
        prompt_manager,
        execution,
        clock: Clock | None = None,
        config: OrchestratorConfig | None = None,
    ):
        self.context_builder = context_builder
        self.memory = memory
        self.retrieval = retrieval
        self.knowledge_graph = knowledge_graph
        self.prompt_manager = prompt_manager
        self.execution = execution
        self.clock = clock or SystemClock()
        self.config = config or OrchestratorConfig()

    def run(self, request: FounderRequest, request_id: str) -> OrchestratorResponse:
        started = self.clock.now()
        completed: list[str] = []
        ctx = None
        memory_items: tuple = ()
        retrieval = None
        graph = None
        rendered = None
        ai = None

        # 2. Build AllyContext (M1) -- required; failure ends the pipeline.
        try:
            ctx = self.context_builder.build(request.founder_id, request.session_id)
            completed.append(BUILD_CONTEXT)
        except Exception as exc:
            return self._finalize(request, request_id, started, completed, BUILD_CONTEXT,
                                  f"context: {exc}", ctx, memory_items, retrieval, graph, rendered, ai)

        # 3. Retrieve Founder Memory (M6) -- continue on failure.
        try:
            result = self.memory.search(
                MemorySearchRequest(founder_id=request.founder_id, limit=self.config.memory_search_limit)
            )
            memory_items = result.items
            completed.append(RETRIEVE_MEMORY)
        except Exception as exc:
            logger.warning("orchestrator: memory retrieval failed; continuing",
                           extra={"stage": RETRIEVE_MEMORY, "error": str(exc)})

        # 4. Retrieve diagnosis-aware knowledge (M3) -- continue on failure.
        try:
            retrieval = self.retrieval.retrieve(ctx, request.message)
            completed.append(RETRIEVE_KNOWLEDGE)
        except Exception as exc:
            logger.warning("orchestrator: retrieval failed; continuing",
                           extra={"stage": RETRIEVE_KNOWLEDGE, "error": str(exc)})

        # 5. Expand knowledge graph (M4) -- continue on failure.
        try:
            graph = self.knowledge_graph.expand_for_context(ctx)
            completed.append(EXPAND_GRAPH)
        except Exception as exc:
            logger.warning("orchestrator: graph expansion failed; continuing",
                           extra={"stage": EXPAND_GRAPH, "error": str(exc)})

        # 6. Build final prompt (M2) -- required; failure ends the pipeline.
        try:
            rendered = self.prompt_manager.render(
                ctx, category=request.response_category, language=request.language
            )
            completed.append(BUILD_PROMPT)
        except Exception as exc:
            return self._finalize(request, request_id, started, completed, BUILD_PROMPT,
                                  f"prompt: {exc}", ctx, memory_items, retrieval, graph, rendered, ai)

        # 7. Execute AI (M5) -- always returns (M5 is itself fail-closed).
        ai = self.execution.execute(AIRequest(prompt=rendered))
        completed.append(EXECUTE_AI)

        # 8. Persist new memory (M6) -- continue on failure. Correlated by request_id.
        try:
            self.memory.store(
                request.founder_id, self.config.persist_memory_type, request.message,
                importance=self.config.persist_importance, session_id=request.session_id,
                correlation_id=request_id, actor="ally",
            )
            completed.append(PERSIST_MEMORY)
        except Exception as exc:
            logger.warning("orchestrator: memory persist failed; continuing",
                           extra={"stage": PERSIST_MEMORY, "error": str(exc)})

        failed_step = None if ai.ok else EXECUTE_AI
        error = None if ai.ok else (ai.error or "ai_execution_failed")
        return self._finalize(request, request_id, started, completed, failed_step, error,
                              ctx, memory_items, retrieval, graph, rendered, ai)

    def _finalize(self, request, request_id, started, completed, failed_step, error,
                  ctx, memory_items, retrieval, graph, rendered, ai) -> OrchestratorResponse:
        finished = self.clock.now()
        duration_ms = round((finished - started).total_seconds() * 1000, 3)

        token_usage = ai.token_usage if ai is not None else TokenUsage()
        provider = ai.metadata.provider if (ai is not None and ai.metadata is not None) else None
        model = ai.metadata.model if (ai is not None and ai.metadata is not None) else None

        metrics = PipelineMetrics(
            memory_reads=len(memory_items),
            retrieval_hits=len(retrieval.items) if retrieval is not None else 0,
            graph_nodes=len(graph.nodes) if graph is not None else 0,
            prompt_version=rendered.version if rendered is not None else None,
            token_usage=token_usage,
        )
        trace = PipelineTrace(
            request_id=request_id, started_at=started, finished_at=finished,
            duration_ms=duration_ms, completed_steps=tuple(completed), failed_step=failed_step,
            provider=provider, model=model, metrics=metrics,
        )
        context = PipelineContext(
            request=request, ally_context=ctx, memory_items=tuple(memory_items),
            retrieval=retrieval, graph=graph, rendered_prompt=rendered, ai_response=ai,
        )
        ok = bool(ai is not None and ai.ok)
        return OrchestratorResponse(
            request_id=request_id, ok=ok,
            answer=ai.content if ok else "",
            response_type=ai.response_type if ok else "none",
            confidence=ai.confidence if ok else None,
            citations=ai.citations if ok else (),
            trace=trace, context=context, error=error,
        )
