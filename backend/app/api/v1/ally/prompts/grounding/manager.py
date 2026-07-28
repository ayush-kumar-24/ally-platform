"""GroundedPromptManager (M2.1) -- the additive grounded renderer.

It SUBCLASSES the frozen M2 PromptManager and reuses its selection, validation and
interpolation verbatim (`_resolve`, `_validate_required`, `_interpolate`). It adds
exactly one method, `render_grounded`, whose single required input is a
GroundingSource (the orchestrator's PipelineContext). Prompt construction stays here,
in the prompt layer -- the orchestrator only hands over the context bundle.

Backward compatibility: the inherited `render(context, ...)` is untouched, so the
original M2 templates keep working through the same class. Grounded templates live
under a distinct category (`*_grounded`) in the grounded repository, so grounded
selection can never collide with the frozen v1 path.
"""

from __future__ import annotations

from app.api.v1.ally.prompts.grounding.errors import GroundingError
from app.api.v1.ally.prompts.grounding.grounded_variables import grounded_variables
from app.api.v1.ally.prompts.grounding.source import GroundingSource
from app.api.v1.ally.prompts.manager import _DEFAULT_LANGUAGE, PromptManager
from app.api.v1.ally.prompts.schemas import PromptSelection, RenderedPrompt

GROUNDED_SUFFIX = "_grounded"


class GroundedPromptManager(PromptManager):
    def render_grounded(
        self,
        source: GroundingSource,
        *,
        category: str | None = None,
        language: str | None = None,
        version: int | None = None,
        variant: str | None = None,
    ) -> RenderedPrompt:
        """Build one grounded RenderedPrompt from `source`.

        Category/language default to the request's own values, so the orchestrator
        can call this with just the PipelineContext. Distress remains context-driven
        (never caller-driven). Fails closed if there is no AllyContext to ground in,
        and -- via the inherited validation/interpolation -- on any missing variable.
        """
        ctx = source.ally_context
        if ctx is None:
            raise GroundingError("diagnosis_answer_grounded", "ally_context is required")

        base_category = category or source.request.response_category
        grounded_category = self._as_grounded(base_category)
        language = language or getattr(source.request, "language", None) or _DEFAULT_LANGUAGE

        selection = PromptSelection(
            category=grounded_category,
            stage=ctx.founder.stage_name,
            distress_mode=ctx.is_distress,
            language=language,
            version=version,
            variant=variant,
        )
        template = self._resolve(selection)              # inherited M2 selection
        variables = grounded_variables(source)           # base M1 vars + grounding blocks
        self._validate_required(template, variables)     # inherited M2 validation
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

    @staticmethod
    def _as_grounded(category: str) -> str:
        return category if category.endswith(GROUNDED_SUFFIX) else category + GROUNDED_SUFFIX
