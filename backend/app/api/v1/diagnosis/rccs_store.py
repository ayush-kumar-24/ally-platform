"""Database adapter for the RCCS evidence trail.

A separate module rather than more methods on `DiagnosisRepository` for two
reasons. The blast radius stays small -- `repository.py` carries unrelated
in-flight work -- and, more importantly, every call here DEGRADES rather than
raises. `root_cause_evidence_events` ships in a migration that has NOT been run
against production (see 2026_09_23_1200-c3f8a91d4e72), so on production today
every read returns empty and every write is a logged no-op.

That is deliberate and it is the honest shape: the adaptive loop must behave
identically whether or not the trail persists, because RCCS is recomputed from
the session's answers on every pass anyway. Persistence buys the REPORT its
explanation of a score, and an audit trail that survives a restart. It does not
buy the loop its correctness.

Nothing here decides anything. The scoring model is `rccs.py`; the stopping rule
is `completion.py`; this module only moves rows.
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.v1.diagnosis.rccs import EvidenceDirection, EvidenceEvent, RCCSState
from app.core.logger import logger
from app.models.enums import ScoreLabel

__all__ = ["RCCSStore"]


class RCCSStore:
    def __init__(self, db: Session):
        self.db = db

    # --- Catalogue lookups ------------------------------------------------

    def question_edges(self, question_ids: tuple[int, ...]) -> dict[int, dict]:
        """For each question: its root cause, its problem, its pillar, its siblings.

        One query rather than one per question -- this runs after every answer.

        The SIBLING set is every OTHER root cause filed under the same
        `problems.problem_id`. That is the only multi-cause edge the schema
        actually has; nothing here infers an association from names, embeddings
        or catalogue adjacency.
        """
        if not question_ids:
            return {}
        try:
            rows = self.db.execute(
                text(
                    """
                    SELECT q.question_id,
                           q.root_cause_id,
                           q.problem_id,
                           p.pillar_id,
                           COALESCE(
                               array_agg(rc.root_cause_id)
                               FILTER (WHERE rc.root_cause_id <> q.root_cause_id),
                               '{}'
                           ) AS sibling_ids
                      FROM questions q
                      JOIN problems p    ON p.problem_id = q.problem_id
                      LEFT JOIN root_causes rc ON rc.problem_id = q.problem_id
                     WHERE q.question_id = ANY(:qids)
                     GROUP BY q.question_id, q.root_cause_id, q.problem_id, p.pillar_id
                    """
                ),
                {"qids": list(question_ids)},
            ).all()
        except Exception as exc:                               # noqa: BLE001
            logger.warning("RCCS question edges unavailable", extra={"error": str(exc)})
            return {}

        return {
            r.question_id: {
                "root_cause_id": r.root_cause_id,
                "problem_id": r.problem_id,
                "pillar_id": r.pillar_id,
                "sibling_ids": tuple(r.sibling_ids or ()),
            }
            for r in rows
        }

    def askable_question_counts(self, root_cause_ids: tuple[int, ...]) -> dict[int, int]:
        """root_cause_id -> how many questions the catalogue holds for it.

        This is the DENOMINATOR of coverage-relative RCCS, so it is the number
        that decides what "fully investigated" means for each cause. Counted from
        the live catalogue rather than cached: the bank is the authority on what
        could have been asked, and a stale count would silently change every
        score built on it.

        Returns {} on failure; `RCCSState` then falls back to the questions
        actually answered, which degrades the score rather than breaking it.
        """
        if not root_cause_ids:
            return {}
        try:
            rows = self.db.execute(
                text(
                    "SELECT root_cause_id, count(*) AS n FROM questions "
                    "WHERE root_cause_id = ANY(:ids) GROUP BY root_cause_id"
                ),
                {"ids": list(root_cause_ids)},
            ).all()
        except Exception as exc:                               # noqa: BLE001
            logger.warning("Askable question counts unavailable; RCCS will fall "
                           "back to answered questions", extra={"error": str(exc)})
            return {}
        return {r.root_cause_id: r.n for r in rows}

    def problem_of_root_causes(self, root_cause_ids: tuple[int, ...]) -> dict[int, int]:
        """root_cause_id -> problem_id, for the quality gate's explanation check."""
        if not root_cause_ids:
            return {}
        try:
            rows = self.db.execute(
                text(
                    "SELECT root_cause_id, problem_id FROM root_causes "
                    "WHERE root_cause_id = ANY(:ids)"
                ),
                {"ids": list(root_cause_ids)},
            ).all()
        except Exception as exc:                               # noqa: BLE001
            logger.warning("RCCS problem map unavailable", extra={"error": str(exc)})
            return {}
        return {r.root_cause_id: r.problem_id for r in rows if r.problem_id is not None}

    def anchor_problem_ids(self, session_id: int) -> frozenset[int]:
        """The founder's presenting complaint, in catalogue terms.

        Non-Green answers map through `questions.problem_id` to the problems the
        symptom detector already works from, so this is the same anchor the rest
        of the pipeline uses -- not a second, parallel notion of "the problem".

        A Green answer is excluded: it is evidence the problem is ABSENT, and an
        absent problem is not something the diagnosis owes an explanation for.
        """
        try:
            rows = self.db.execute(
                text(
                    """
                    SELECT DISTINCT q.problem_id
                      FROM answers a
                      JOIN questions q ON q.question_id = a.question_id
                     WHERE a.session_id = :sid
                       AND a.score_label IS NOT NULL
                       AND a.score_label <> 'not_applicable'
                       AND a.score_label <> 'green'
                       AND q.problem_id IS NOT NULL
                    """
                ),
                {"sid": session_id},
            ).all()
        except Exception as exc:                               # noqa: BLE001
            logger.warning("RCCS anchor problems unavailable", extra={"error": str(exc)})
            return frozenset()
        return frozenset(r.problem_id for r in rows)

    # --- The trail --------------------------------------------------------

    def record(self, session_id: int, events: tuple[EvidenceEvent, ...]) -> int:
        """Append events. Returns how many rows were written.

        `ON CONFLICT DO NOTHING` against the unique index is the database half of
        RCCS idempotence: a replayed answer writes nothing rather than scoring
        twice. Returns 0 and logs, without raising, when the table is absent --
        which is production's state until the migration runs.
        """
        if not events:
            return 0
        try:
            written = 0
            for e in events:
                result = self.db.execute(
                    text(
                        """
                        INSERT INTO root_cause_evidence_events
                            (session_id, answer_id, question_id, root_cause_id,
                             direction, magnitude, score_label, source, pillar_id,
                             sequence)
                        VALUES
                            (:sid, :aid, :qid, :rcid, :dir, :mag, :label, :src,
                             :pillar, :seq)
                        ON CONFLICT (session_id, answer_id, root_cause_id) DO NOTHING
                        """
                    ),
                    {
                        "sid": session_id,
                        "aid": e.answer_id,
                        "qid": e.question_id,
                        "rcid": e.root_cause_id,
                        "dir": e.direction.value,
                        "mag": e.magnitude,
                        "label": e.score_label.value,
                        "src": e.source,
                        "pillar": e.pillar_id,
                        "seq": e.sequence,
                    },
                )
                written += result.rowcount or 0
            return written
        except Exception as exc:                               # noqa: BLE001
            logger.warning(
                "RCCS evidence trail not persisted (migration c3f8a91d4e72 pending?)",
                extra={"session_id": session_id, "error": str(exc)},
            )
            return 0

    def load_state(self, session_id: int) -> RCCSState | None:
        """Rebuild the RCCS state from the persisted trail, or None if unavailable.

        Replaying the trail reproduces the live scores exactly (pinned by
        `test_rebuilding_state_from_the_trail_reproduces_the_scores`), so this is
        a restore, not an approximation.
        """
        try:
            rows = self.db.execute(
                text(
                    "SELECT answer_id, question_id, root_cause_id, direction, "
                    "magnitude, score_label, source, pillar_id, sequence "
                    "FROM root_cause_evidence_events WHERE session_id = :sid "
                    "ORDER BY sequence, evidence_event_id"
                ),
                {"sid": session_id},
            ).all()
        except Exception as exc:                               # noqa: BLE001
            logger.warning(
                "RCCS trail unreadable; state will be rebuilt from answers",
                extra={"session_id": session_id, "error": str(exc)},
            )
            return None

        # Same catalogue denominator the live loop uses. Without it this would
        # fall back to answered-questions and the selector would score causes
        # differently from the scorer -- two readings of one session.
        askable = self.askable_question_counts(
            tuple(sorted({r.root_cause_id for r in rows}))
        )
        state = RCCSState(askable=askable)
        for r in rows:
            state.apply(
                EvidenceEvent(
                    answer_id=r.answer_id,
                    question_id=r.question_id,
                    root_cause_id=r.root_cause_id,
                    direction=EvidenceDirection(r.direction),
                    magnitude=Decimal(r.magnitude),
                    pillar_id=r.pillar_id,
                    score_label=ScoreLabel(r.score_label),
                    source=r.source,
                    sequence=r.sequence,
                )
            )
        return state
