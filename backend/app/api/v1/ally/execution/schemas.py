"""Typed DTOs for the AI Execution Layer (Phase 5, Milestone 5).

All immutable frozen dataclasses. The layer is provider-agnostic: nothing here (or
anywhere outside the provider implementation) names a vendor. `AIResponse` is the
single validated output; a fail-closed empty response is a normal `AIResponse` with
`ok=False` and empty content -- never fabricated fallback text.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Any, Mapping

from app.api.v1.ally.prompts.schemas import RenderedPrompt


class ResponseType(str, Enum):
    ANSWER = "answer"
    CLARIFICATION = "clarification"
    DISTRESS_SUPPORT = "distress_support"
    REFUSAL = "refusal"


@dataclass(frozen=True)
class TokenUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    @classmethod
    def of(cls, prompt: int, completion: int) -> "TokenUsage":
        return cls(prompt, completion, prompt + completion)


class MediaKind(str, Enum):
    IMAGE = "image"
    DOCUMENT = "document"


@dataclass(frozen=True)
class MediaBlock:
    """One piece of non-text content for the model to look at, alongside the
    prompt -- a screenshot, or the pages of a scanned PDF.

    Lives here rather than with the attachment code that builds it because it is
    a transport type: it is what a provider is handed, in the same
    vendor-neutral terms as ProviderRequest itself. An adapter whose vendor
    takes no media simply ignores it, and the turn degrades to the text prompt
    describing the file by name -- never to a lost question.

    `pages_sent` / `pages_total` differ only when a document was truncated to
    keep one upload from spending a founder's whole daily token allowance. The
    prompt states that out loud; a model handed 5 pages of 40 with no note will
    answer as though it saw all 40.
    """

    kind: MediaKind
    mime_type: str
    data_base64: str
    filename: str
    pages_sent: int | None = None
    pages_total: int | None = None

    @property
    def truncated(self) -> bool:
        return (
            self.pages_sent is not None
            and self.pages_total is not None
            and self.pages_sent < self.pages_total
        )


# --- Provider-facing (vendor-neutral) --------------------------------------


@dataclass(frozen=True)
class ProviderRequest:
    system: str
    user: str
    model: str
    temperature: Decimal
    max_tokens: int
    #: Files for the model to look at this turn. Empty for every text-only turn,
    #: which is nearly all of them, so an adapter that ignores this field behaves
    #: exactly as it did before media existed.
    media: tuple[MediaBlock, ...] = ()


@dataclass(frozen=True)
class ProviderResponse:
    content: str                      # raw response body (expected JSON)
    finish_reason: str
    token_usage: TokenUsage
    model: str
    provider: str


@dataclass(frozen=True)
class ProviderHealth:
    healthy: bool
    detail: str = ""


@dataclass(frozen=True)
class ProviderMetadata:
    name: str
    models: tuple[str, ...]
    supports_json: bool = True
    max_context: int = 8192


# --- Execution-facing -------------------------------------------------------


@dataclass(frozen=True)
class AIRequest:
    """What the Execution Service receives. The prompt (built upstream by M2 from
    M1/M3/M4) is what gets sent; the optional overrides let a caller pin a
    provider/model/params. Routing signals (distress, category) are read off the
    prompt -- the execution layer never rebuilds a prompt.

    `reasoning_required` is the one exception: it's set by the caller (chat
    execution), not read off the prompt, because it depends on the founder's
    raw message text plus whether grounded data was actually available for
    this turn -- neither of which the prompt/router should need to know about
    to stay vendor- and content-neutral. See
    app.ai_chat.execution.reasoning_classifier.needs_reasoning. Distress wins
    outright over this if both are true (see AIRouter.route)."""

    prompt: RenderedPrompt
    response_type: str = ResponseType.ANSWER.value
    requested_provider: str | None = None
    requested_model: str | None = None
    temperature: Decimal | None = None
    max_tokens: int | None = None
    reasoning_required: bool = False
    #: Set by chat execution from the conversation's attachments, not read off
    #: the prompt -- RenderedPrompt is text and its content fingerprint is over
    #: text, and widening it to cover bytes would change what two prompts being
    #: "equal" means for every caller that has nothing to do with files.
    media: tuple[MediaBlock, ...] = ()


@dataclass(frozen=True)
class RoutingDecision:
    provider: str
    model: str
    temperature: Decimal
    max_tokens: int


@dataclass(frozen=True)
class ExecutionMetadata:
    provider: str
    model: str
    temperature: Decimal
    max_tokens: int
    attempts: int
    succeeded: bool
    timed_out: bool = False
    error: str | None = None


@dataclass(frozen=True)
class AIResponse:
    """The single validated output. `ok=False` with empty content is the
    fail-closed result (timeout, provider failure, invalid response)."""

    ok: bool
    content: str
    response_type: str
    confidence: Decimal | None
    citations: tuple[str, ...]
    token_usage: TokenUsage
    metadata: ExecutionMetadata | None = None
    error: str | None = None
    extra: Mapping[str, Any] = field(default_factory=dict)

    @property
    def is_empty(self) -> bool:
        return not self.ok or not self.content
