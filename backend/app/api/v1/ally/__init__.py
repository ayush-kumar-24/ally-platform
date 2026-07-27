"""Ally AI Layer (Phase 5).

The conversational AI that sits ABOVE the frozen diagnosis system. It never
recomputes or modifies any reasoning output -- it reads the persisted results
(founder_reports, internal_intelligence_reports, detected_root_causes, sessions)
and grounds every answer in them.

Milestone 1 delivers the Context Builder (see `ally.context`): the read-model
that assembles a typed, immutable AllyContext every other Phase-5 component
consumes. It is the single enforcement point for "the AI never ignores diagnosis
context" -- downstream layers must refuse to answer when the context is not
answerable.
"""
