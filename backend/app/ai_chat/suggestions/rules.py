"""Deterministic suggestion rules (Phase 6, Milestone 5, Part 3).

Each rule is a pure function of the SuggestionContext returning zero or more
SuggestionDrafts. No LLM, no I/O, no randomness -- identical context yields identical
drafts. Rules describe WHAT to suggest and WHY; the engine assigns id/time and the
ranking service orders/dedupes them.
"""

from __future__ import annotations

from app.ai_chat.suggestions.schemas import (
    SuggestionContext,
    SuggestionDraft,
    SuggestionPriority as P,
    SuggestionReason,
    SuggestionSource as S,
    SuggestionType as T,
)

_LONG_CONVERSATION = 8   # messages


def _ally_context(ctx: SuggestionContext):
    window = ctx.context_window
    return getattr(window, "ally_context", None) if window is not None else None


def _top_topic(ctx: SuggestionContext) -> str:
    ally = _ally_context(ctx)
    root_causes = getattr(ally, "root_causes", ()) if ally is not None else ()
    for rc in root_causes:
        if getattr(rc, "is_top_finding", False) and getattr(rc, "name", None):
            return rc.name
    return "your question"


def _answered(ctx: SuggestionContext) -> bool:
    return ctx.ai_response is not None and bool(getattr(ctx.ai_response, "ok", False))


def rule_follow_up(ctx: SuggestionContext) -> list[SuggestionDraft]:
    if not _answered(ctx):
        return []
    return [SuggestionDraft(
        T.FOLLOW_UP, "Ask a follow-up question",
        f"Want to go deeper on {_top_topic(ctx)}?", P.MEDIUM, S.AI_RESPONSE,
        SuggestionReason("ai_answered", "An answer was provided; a follow-up can deepen it."),
        "follow_up", base_relevance=0.6)]


def rule_clarification(ctx: SuggestionContext) -> list[SuggestionDraft]:
    if _answered(ctx):
        return []
    if ctx.ai_response is None:
        return []                                     # nothing to clarify without a turn
    return [SuggestionDraft(
        T.CLARIFICATION, "Rephrase or add detail",
        "The assistant couldn't fully answer. Try rephrasing or adding context.",
        P.HIGH, S.AI_RESPONSE,
        SuggestionReason("no_answer", "The AI response was not a confident answer."),
        "clarification", base_relevance=0.85)]


def rule_missing_information(ctx: SuggestionContext) -> list[SuggestionDraft]:
    ally = _ally_context(ctx)
    if ally is None or getattr(ally, "has_diagnosis", True):
        return []
    return [SuggestionDraft(
        T.MISSING_INFORMATION, "Complete your diagnosis",
        "A completed diagnosis lets Ally ground answers in your data.", P.HIGH, S.CONTEXT,
        SuggestionReason("no_diagnosis", "No completed diagnosis is available for grounding."),
        "missing_information", base_relevance=0.8)]


def rule_summarization(ctx: SuggestionContext) -> list[SuggestionDraft]:
    if ctx.conversation.message_count < _LONG_CONVERSATION:
        return []
    return [SuggestionDraft(
        T.SUMMARIZATION, "Summarize this conversation",
        "This chat is getting long -- a summary can capture the key points.",
        P.MEDIUM, S.CONVERSATION,
        SuggestionReason("long_conversation",
                         f"The conversation has {ctx.conversation.message_count} messages."),
        "summarization", base_relevance=0.5)]


def rule_attachment_review(ctx: SuggestionContext) -> list[SuggestionDraft]:
    active = [a for a in ctx.attachments if getattr(a, "is_active", True)]
    if not active:
        return []
    return [SuggestionDraft(
        T.ATTACHMENT_REVIEW, "Review attached files",
        f"You've attached {len(active)} file(s) -- ask Ally to reference them.",
        P.MEDIUM, S.ATTACHMENT,
        SuggestionReason("attachments_present", f"{len(active)} active attachment(s)."),
        "attachment_review", base_relevance=0.55)]


def rule_link_discussion(ctx: SuggestionContext) -> list[SuggestionDraft]:
    if not ctx.links:
        return []
    providers = sorted({getattr(l.link_type, "value", str(l.link_type)) for l in ctx.links})
    return [SuggestionDraft(
        T.LINK_DISCUSSION, "Discuss shared links",
        f"You shared {len(ctx.links)} link(s) ({', '.join(providers)}). Want to talk them through?",
        P.MEDIUM, S.LINK,
        SuggestionReason("links_present", f"{len(ctx.links)} link(s) detected."),
        "link_discussion", base_relevance=0.55)]


def rule_continue_conversation(ctx: SuggestionContext) -> list[SuggestionDraft]:
    if ctx.conversation.message_count <= 0:
        return []
    return [SuggestionDraft(
        T.CONTINUE_CONVERSATION, "Continue the conversation",
        "Keep going -- ask your next question whenever you're ready.", P.LOW, S.CONVERSATION,
        SuggestionReason("active_conversation", "The conversation has prior turns."),
        "continue_conversation", base_relevance=0.3)]


def rule_goal_reminder(ctx: SuggestionContext) -> list[SuggestionDraft]:
    ally = _ally_context(ctx)
    diagnosis = getattr(ally, "diagnosis", None) if ally is not None else None
    if diagnosis is None:
        return []
    steps = tuple(getattr(diagnosis, "next_steps", ()) or getattr(diagnosis, "priority_actions", ()))
    if not steps:
        return []
    return [SuggestionDraft(
        T.GOAL_REMINDER, "Next recommended step", f"From your diagnosis: {steps[0]}",
        P.HIGH, S.CONTEXT,
        SuggestionReason("has_next_step", "The diagnosis defines a next step."),
        "goal_reminder", base_relevance=0.7)]


DEFAULT_RULES = (
    rule_follow_up,
    rule_clarification,
    rule_missing_information,
    rule_summarization,
    rule_attachment_review,
    rule_link_discussion,
    rule_continue_conversation,
    rule_goal_reminder,
)
