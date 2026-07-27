"""Prompt template loading.

The repository is a pure data-access seam: it LOADS templates and nothing else --
no selection logic, no rendering, no interpolation. Selection is the Manager's job.

`InMemoryPromptRepository` is the default implementation and the one the tests use.
A future `DbPromptRepository` (reading the prompt_library table) can implement the
same interface without any change to the Manager -- which is exactly why the
Manager depends on this interface and never on the database.
"""

from __future__ import annotations

import abc
from collections.abc import Iterable

from app.api.v1.ally.prompts.schemas import PromptTemplate


class PromptRepository(abc.ABC):
    """Loads stored prompt templates. Loading only -- no business logic."""

    @abc.abstractmethod
    def list_templates(self) -> tuple[PromptTemplate, ...]:
        """Every available template. The Manager filters/selects from these."""
        raise NotImplementedError


class InMemoryPromptRepository(PromptRepository):
    """Holds templates in memory. Source-agnostic: seed it from the built-in
    library, a config loader, or a future DB adapter."""

    def __init__(self, templates: Iterable[PromptTemplate]):
        self._templates = tuple(templates)

    def list_templates(self) -> tuple[PromptTemplate, ...]:
        return self._templates
