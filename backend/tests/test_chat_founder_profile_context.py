"""Ally chat is told who the founder is.

Chat had every other grounding source -- diagnosis, memory, retrieval, graph,
uploaded files, tasks -- and not the onboarding profile. The data was in
`founders` the whole time; nothing put it in the prompt. Confirmed in
production, where Ally told a founder who HAD completed onboarding:

    "I don't have your problem statement, your target customer, your market
     size, or any product details. Those weren't part of what got saved from
     your onboarding -- only the diagnosis came through."

Every assertion here is about that sentence never being true again.

The prompt-side tests build a real ConversationContextWindow rather than a
stub: the bug was a field failing to travel from the window to the rendered
variables, and a stub shaped by hand is exactly the thing that would not have
caught it.
"""

from types import SimpleNamespace

from app.ai_chat.builders.context_window import ContextWindowBuilder
from app.ai_chat.schemas.chat import ConversationContextWindow, GroundingRequest
from app.api.v1.ally.prompts.grounding.grounded_variables import grounded_variables


def _builder(**overrides):
    kwargs = dict(
        conversation_service=None, memory=None, retrieval=None,
        knowledge_graph=None, attachments=None, planning=None,
        founder_profile=None,
    )
    kwargs.update(overrides)
    return ContextWindowBuilder(**kwargs)


def _window(profile_text: str) -> ConversationContextWindow:
    return ConversationContextWindow(
        request=GroundingRequest(message="who am I?", language="en",
                                 response_category="general_chat"),
        # Minimal AllyContext: grounded_variables reads schema_version and the
        # founder/diagnosis fields off it. Only the profile block is under test.
        ally_context=SimpleNamespace(
            schema_version="v1", has_diagnosis=False,
            founder=SimpleNamespace(full_name="Rohan", stage_name="Growth",
                                    industry="SaaS", founder_id=42,
                                    stage_id=5, stage_groups=()),
            diagnosis=None, root_causes=(), business_health=None,
            internal_intelligence=None),
        memory_items=(),
        retrieval=None,
        graph=None,
        conversation_context=None,
        current_message="who am I?",
        profile_text=profile_text,
    )


# --- the source: does the profile get loaded at all? ---------------------


def test_profile_is_loaded_for_the_right_founder():
    text, ok = _builder(
        founder_profile=lambda fid: f"FOUNDER CONTEXT\nStage: Growth (founder {fid})"
    )._safe_profile(42)

    assert ok is True
    assert "Stage: Growth" in text
    assert "founder 42" in text      # the conversation's founder, not a default


def test_profile_failure_degrades_instead_of_killing_the_turn():
    """Every source in this builder fails closed. A missing profile costs Ally
    context; it must never cost the founder their message."""
    def boom(_founder_id):
        raise RuntimeError("db gone")

    text, ok = _builder(founder_profile=boom)._safe_profile(42)

    assert ok is False
    assert text == ""


def test_no_profile_source_is_not_an_error():
    """Other GroundingSource implementers (tests, the orchestrator) supply
    none. Additive and optional, same as attachments and tasks."""
    text, ok = _builder(founder_profile=None)._safe_profile(42)

    assert ok is False
    assert text == ""


# --- the prompt: does it actually arrive? --------------------------------


def test_the_prompt_actually_carries_the_profile():
    """Holding it on the window is not enough -- it has to reach the variables
    the template renders, which is the step that was missing."""
    variables = grounded_variables(
        _window("FOUNDER CONTEXT\nBuilding: ComplyEdge"))

    assert "ComplyEdge" in variables["founder_profile_block"]


def test_missing_profile_says_so_rather_than_going_blank():
    """A blank block invites the model to fill the silence. Saying onboarding
    is incomplete lets Ally point the founder at the fix instead of denying the
    data exists, which is what it did in production."""
    variables = grounded_variables(_window(""))

    assert variables["founder_profile_block"] == "Onboarding profile not completed."


def test_general_chat_template_renders_the_profile_slot():
    """The template and its required_variables must agree -- a required
    variable with no slot, or a slot with no variable, breaks rendering."""
    from app.api.v1.ally.prompts.grounding import library

    prompts = [v for v in vars(library).values()
               if hasattr(v, "user_prompt") and hasattr(v, "required_variables")]
    rendering = [p for p in prompts if "{{founder_profile_block}}" in p.user_prompt]

    assert rendering, "no grounded prompt renders the founder profile block"
    for prompt in rendering:
        assert "founder_profile_block" in prompt.required_variables
