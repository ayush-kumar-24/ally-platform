"""Strongly-typed DTOs for the Ally prompt layer.

All immutable frozen dataclasses. A PromptTemplate is pure data (no logic), so new
templates are added as data -- in the DB, a config file or the built-in library --
without touching the Manager. The Manager consumes these and produces a
RenderedPrompt; it never returns raw strings.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Mapping

# Interpolation uses double braces so template bodies can contain literal single
# braces (e.g. JSON examples) without being treated as variables: {{variable}}.


@dataclass(frozen=True)
class PromptMetadata:
    """Descriptive, non-functional attributes of a template.

    `variant` is the A/B-testing hook: two templates that differ only by variant
    can coexist for the same selection and the Manager picks the requested one.
    """

    author: str | None = None
    description: str | None = None
    tags: tuple[str, ...] = ()
    variant: str | None = None
    extra: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PromptTemplate:
    """One stored prompt template. Pure data.

    `required_variables` are the context variables the template needs; the Manager
    validates them before rendering and fails closed if any is absent. `stage`
    None means the template applies to any stage (a wildcard); a specific stage
    token is preferred over the wildcard when both match.
    """

    template_key: str
    version: int
    category: str
    system_prompt: str
    user_prompt: str
    required_variables: tuple[str, ...] = ()
    stage: str | None = None
    distress_mode: bool = False
    language: str = "en"
    metadata: PromptMetadata = field(default_factory=PromptMetadata)


@dataclass(frozen=True)
class PromptSelection:
    """A resolved request for a template. Built by the Manager from AllyContext
    plus the caller's intent; `version` None means 'latest active'."""

    category: str
    stage: str | None = None
    distress_mode: bool = False
    language: str = "en"
    version: int | None = None
    variant: str | None = None


@dataclass(frozen=True)
class RenderedPrompt:
    """The Manager's output: an interpolated, provider-agnostic prompt plus the
    provenance (which template/version and which variable values were used).
    Deterministic: equal inputs produce an equal RenderedPrompt."""

    template_key: str
    version: int
    category: str
    language: str
    distress_mode: bool
    system_prompt: str
    user_prompt: str
    variables: Mapping[str, str]
    metadata: PromptMetadata
    # Deterministic content fingerprint over the rendered (system, user) payload --
    # the exact text a provider would receive. Derived (init=False) so it is always
    # correct and never passed inconsistently. Stable across processes (SHA-256 of a
    # canonical JSON), unlike Python's per-process hash(). Use it to cache
    # completions, dedupe, and detect that a prompt's content changed.
    prompt_fingerprint: str = field(default="", init=False)

    def __post_init__(self) -> None:
        payload = json.dumps(
            {"system": self.system_prompt, "user": self.user_prompt},
            sort_keys=True,
            ensure_ascii=False,
        )
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        object.__setattr__(self, "prompt_fingerprint", digest)
