"""Prompt Manager -- selects, validates and interpolates a template into a
RenderedPrompt from the immutable AllyContext.

Boundaries (enforced by imports): this module imports ONLY the prompt schemas,
errors, repository interface and the context flattener. It does NOT touch the
database, an LLM, RAG, memory, the router or the knowledge graph -- those are
later milestones. It is pure prompt preparation.

Determinism: for a given (context, category, language, version, variant) and a
given repository, the RenderedPrompt is byte-identical on every call.
"""

from __future__ import annotations

import re

from app.api.v1.ally.context.schemas import AllyContext
from app.api.v1.ally.prompts.context_variables import context_variables
from app.api.v1.ally.prompts.errors import (
    MissingPromptVariableError,
    PromptNotFoundError,
    RenderingError,
    TemplateVersionError,
    UnsupportedLanguageError,
)
from app.api.v1.ally.prompts.repository import PromptRepository
from app.api.v1.ally.prompts.schemas import (
    PromptSelection,
    PromptTemplate,
    RenderedPrompt,
)

_DEFAULT_LANGUAGE = "en"
_PLACEHOLDER = re.compile(r"\{\{\s*([A-Za-z0-9_]+)\s*\}\}")


class PromptManager:
    def __init__(
        self,
        repository: PromptRepository,
        *,
        supported_languages: frozenset[str] = frozenset({_DEFAULT_LANGUAGE}),
    ):
        self.repository = repository
        self.supported_languages = supported_languages

    def render(
        self,
        context: AllyContext,
        *,
        category: str,
        language: str = _DEFAULT_LANGUAGE,
        version: int | None = None,
        variant: str | None = None,
    ) -> RenderedPrompt:
        """Build the prompt for `category`, grounded in `context`.

        Distress is context-driven, never caller-driven: if the founder is in
        distress the manager selects the distress template (wellbeing first). Fails
        closed on a missing template, missing variable, bad version or unsupported
        language.
        """
        selection = PromptSelection(
            category=category,
            stage=context.founder.stage_name,
            distress_mode=context.is_distress,
            language=language,
            version=version,
            variant=variant,
        )
        template = self._resolve(selection)

        variables = context_variables(context)
        self._validate_required(template, variables)
        system = self._interpolate(template.system_prompt, variables, template)
        user = self._interpolate(template.user_prompt, variables, template)

        return RenderedPrompt(
            template_key=template.template_key,
            version=template.version,
            category=template.category,
            language=template.language,
            distress_mode=template.distress_mode,
            system_prompt=system,
            user_prompt=user,
            variables=dict(variables),
            metadata=template.metadata,
        )

    # --- Selection (business logic lives here, not in the repository) ------

    def _resolve(self, selection: PromptSelection) -> PromptTemplate:
        if selection.language not in self.supported_languages:
            raise UnsupportedLanguageError(
                selection.language, sorted(self.supported_languages)
            )

        candidates = [
            t
            for t in self.repository.list_templates()
            if t.category == selection.category
            and t.language == selection.language
            and t.distress_mode == selection.distress_mode
            and (t.stage is None or t.stage == selection.stage)
            and (selection.variant is None or t.metadata.variant == selection.variant)
        ]
        if not candidates:
            raise PromptNotFoundError(self._describe(selection))

        if selection.version is not None:
            exact = [t for t in candidates if t.version == selection.version]
            if not exact:
                raise TemplateVersionError(
                    selection.category,
                    selection.version,
                    sorted({t.version for t in candidates}),
                )
            candidates = exact

        # Deterministic: stage-specific over wildcard, then highest version, then
        # template_key as a stable final tiebreak.
        candidates.sort(key=lambda t: (t.stage is None, -t.version, t.template_key))
        return candidates[0]

    def _describe(self, s: PromptSelection) -> str:
        return (
            f"category={s.category!r} stage={s.stage!r} distress={s.distress_mode} "
            f"language={s.language!r} variant={s.variant!r}"
        )

    # --- Validation + interpolation ---------------------------------------

    def _validate_required(
        self, template: PromptTemplate, variables: dict[str, str]
    ) -> None:
        missing = [v for v in template.required_variables if v not in variables]
        if missing:
            raise MissingPromptVariableError(template.template_key, sorted(missing))

    def _interpolate(
        self, body: str, variables: dict[str, str], template: PromptTemplate
    ) -> str:
        if body is None:
            raise RenderingError(template.template_key, "template body is None")
        missing: list[str] = []

        def repl(match: re.Match) -> str:
            name = match.group(1)
            if name not in variables:
                missing.append(name)
                return match.group(0)
            return variables[name]

        try:
            rendered = _PLACEHOLDER.sub(repl, body)
        except Exception as exc:  # malformed template body, not a missing variable
            raise RenderingError(template.template_key, str(exc)) from exc

        if missing:
            raise MissingPromptVariableError(template.template_key, sorted(set(missing)))
        return rendered
