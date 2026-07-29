"""SuggestionRankingService (Phase 6, Milestone 5, Part 4).

Deterministic ranking: de-duplicate by dedup_key (keep the strongest), then order by
priority, relevance, recency with stable tie-breaks, then cap at a maximum count.
Same input -> same order, every time. Pure -- no clock, no id, no I/O.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from app.ai_chat.suggestions.schemas import PRIORITY_WEIGHT, TYPE_ORDER, Suggestion

_DEFAULT_MAX = 5


@dataclass(frozen=True)
class RankResult:
    ranked: tuple[Suggestion, ...]
    suppressed_duplicates: int
    limited: bool


def _sort_key(s: Suggestion):
    # Highest priority first, then relevance, then most-recent, then a stable
    # type/title/dedup tiebreak so ordering never depends on ids or insertion order.
    return (
        -PRIORITY_WEIGHT[s.priority],
        -s.relevance_score,
        -s.created_at.timestamp(),
        TYPE_ORDER.get(s.suggestion_type.value, 99),
        s.title,
        s.dedup_key,
    )


class SuggestionRankingService:
    def __init__(self, *, max_suggestions: int = _DEFAULT_MAX):
        self.max_suggestions = max_suggestions

    def rank(self, suggestions: list[Suggestion], *, max_count: int | None = None) -> RankResult:
        limit = self.max_suggestions if max_count is None else max_count
        deduped = self._deduplicate(suggestions)
        suppressed = len(suggestions) - len(deduped)

        ordered = sorted(deduped, key=_sort_key)
        limited = len(ordered) > limit
        ranked = tuple(replace(s, rank=i) for i, s in enumerate(ordered[:limit]))
        return RankResult(ranked=ranked, suppressed_duplicates=suppressed, limited=limited)

    @staticmethod
    def _deduplicate(suggestions: list[Suggestion]) -> list[Suggestion]:
        """Keep, per dedup_key, the strongest (priority then relevance). Deterministic
        even when two share a key."""
        best: dict[str, Suggestion] = {}
        for s in suggestions:
            current = best.get(s.dedup_key)
            if current is None or _strength(s) > _strength(current):
                best[s.dedup_key] = s
        return list(best.values())


def _strength(s: Suggestion) -> tuple:
    return (PRIORITY_WEIGHT[s.priority], s.relevance_score)
