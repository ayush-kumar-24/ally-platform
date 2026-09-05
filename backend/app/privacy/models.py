"""Domain DTOs for the Privacy Center (data-subject rights).

Immutable frozen dataclasses -- the service returns these, never ORM rows, so the
persistence layer stays swappable.

Mapping to the rights being exercised:
    ExportBundle      GDPR Art 15 (access) + Art 20 (portability); DPDP s.11
    PrivacyState      Art 18 (restriction) + Art 17 (erasure) status for a founder
    PrivacyAction     the receipt returned for any right exercised, so the founder
                      always gets a reference and a due date rather than a silent OK
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class ExportBundle:
    """Everything Ally holds about one founder, assembled for download."""

    founder_id: int
    generated_at: datetime
    # section name -> rows. A section present with an empty list means "we hold
    # nothing here", which is materially different from the section being absent.
    sections: dict[str, Any] = field(default_factory=dict)
    #: "access" (Art 15 -- everything we hold, including Ally's own analysis) or
    #: "portability" (Art 20 -- only what the founder provided). Carried on the
    #: bundle so the downloaded file states which of the two it is; a founder
    #: handing the file to another service should not have to guess.
    kind: str = "access"

    @property
    def record_count(self) -> int:
        return sum(len(v) if isinstance(v, list) else 1 for v in self.sections.values())


@dataclass(frozen=True)
class DataSummary:
    """A lighter answer to "what does Ally hold about me" than a full export --
    counts per category, not the raw rows. Backs the self-service "View data
    summary" action: originally a queued request nothing in the codebase could
    ever resolve (no email delivery exists), turned instant/self-serve instead
    since counting what gather_export already found needs no human review."""

    founder_id: int
    generated_at: datetime
    counts: dict[str, int] = field(default_factory=dict)

    @property
    def total_records(self) -> int:
        return sum(self.counts.values())

    @property
    def categories(self) -> list[dict]:
        """The same counts, grouped and named for the person reading them.

        `counts` is keyed by export section, which is keyed by database table:
        `founder_memory_events: 24` is a true statement that tells a founder
        nothing. This is the founder-facing view of the same numbers -- six
        groups in the order someone would ask about them, each with a plain
        sentence saying what it is.

        Grouped here rather than in the UI so the Privacy Center, the help bot
        and any future export cover-sheet all describe a founder's data with the
        same words. Two surfaces free-handing their own category names is how
        they end up disagreeing.
        """
        groups: tuple[tuple[str, str, str, tuple[str, ...]], ...] = (
            ("profile", "Your profile and settings",
             "Your name, contact details, stage, and how you have set Ally up.",
             ("founder_profile", "settings", "plans")),
            ("diagnosis", "Your diagnosis",
             "The questions you answered, including Founder DNA and your current problem.",
             ("diagnosis_sessions", "diagnosis_answers", "founder_dna_answers",
              "current_problem_answers")),
            ("analysis", "Your reports and what Ally worked out",
             "Your reports, the root causes Ally identified, and what it remembers about you.",
             ("reports", "detected_root_causes", "stage_assessments",
              "founder_context", "founder_memory", "founder_memory_events")),
            ("conversations", "Conversations with Ally",
             "Every chat you have had with Ally, and the messages inside them.",
             ("conversations", "messages")),
            ("planning", "Goals and tasks",
             "What you set yourself in Plan Your Day, Goals and Vision.",
             ("goals", "tasks")),
            ("account_record", "Your requests and account record",
             "Calls you booked, feedback you sent, your consents, and requests like this one.",
             ("discovery_calls", "feedback", "consents", "privacy_requests",
              "notifications", "token_usage")),
        )

        out: list[dict] = []
        grouped: set[str] = set()
        for key, label, description, sections in groups:
            grouped.update(sections)
            out.append({
                "key": key,
                "label": label,
                "description": description,
                "count": sum(self.counts.get(s, 0) for s in sections),
            })

        # A section added to the export and not to a group above would otherwise
        # vanish from the founder's view while still being held -- the one
        # failure this whole feature exists to prevent. It surfaces instead.
        ungrouped = sum(v for k, v in self.counts.items() if k not in grouped)
        if ungrouped:
            out.append({
                "key": "other",
                "label": "Other records",
                "description": "Everything else Ally holds for your account.",
                "count": ungrouped,
            })
        return out


@dataclass(frozen=True)
class PrivacyState:
    """The founder's current standing under Art 17/18.

    `processing_restricted` pauses AI profiling without touching the account.
    `deletion_scheduled_at` is a future date, not an immediate purge -- see
    PrivacyService.request_account_deletion for why.
    """

    founder_id: int
    processing_restricted: bool
    processing_restricted_at: datetime | None
    deletion_requested_at: datetime | None
    deletion_scheduled_at: datetime | None
    deletion_executed_at: datetime | None = None

    @property
    def deletion_pending(self) -> bool:
        """Requested, and the sweep has not yet run. Distinct from merely
        "requested at some point" -- once executed, the request is history,
        not a pending state that should still gate processing (may_process)
        or read as cancellable."""
        return self.deletion_requested_at is not None and self.deletion_executed_at is None


@dataclass(frozen=True)
class PrivacyAction:
    """Receipt for an exercised right -- logged to privacy_requests.

    The fields below `due_by` exist for the admin resolution path
    (AdminPanelService.resolve_privacy_request): a "queued" request (view_data,
    correct_data) sits pending until an admin acts on it, and these are what
    they act with.
    """

    request_id: int
    founder_id: int
    request_type: str
    status: str
    requested_at: datetime
    due_by: datetime | None = None
    request_details: str | None = None
    processed_by: str | None = None
    processing_notes: str | None = None
    rejection_reason: str | None = None
    completed_at: datetime | None = None
