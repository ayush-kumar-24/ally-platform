"""Founder Pattern / Archetype Engine -- assigns one of the seeded archetypes.

Reads the `archetypes` catalogue (8 rows: e.g. "Operator", "Visionary Builder")
and matches a founder to the best-fit archetype from their own words. Each
archetype carries free-text `assignment_criteria` (behavioural description +
signature phrases) and `key_traits` (decision_style / stress_pattern /
core_motivation); this engine turns those into a comparable signal.

Deterministic core (no LLM): a lexical-overlap match between the founder's answer
text and each archetype's signature phrases + distinctive keywords, normalised to
0..1, best-fit wins with a stable tiebreak. This is intentionally a heuristic --
the accurate assignment is a semantic/LLM job (embed the criteria + the founder's
language, or have the LLM classify), which is the documented seam: swap
`assign` for an embedding/LLM matcher without changing callers. The archetype
embeddings (archetypes.embedding, currently unpopulated) are the intended vehicle.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from app.api.v1.reasoning.repository import ReasoningRepository

_TOKEN = re.compile(r"[a-z]+")
_PHRASE = re.compile(r'["“]([^"”]+)["”]')
_QUANT = Decimal("0.0001")
_PHRASE_WEIGHT = 3  # a signature-phrase hit counts for more than a keyword hit
_MIN_KEYWORD_LEN = 4

# Generic words that carry no archetype signal. Distinctiveness filtering (drop
# tokens shared by many archetypes) removes most domain-common words; this covers
# the residue.
_STOPWORDS = frozenset(
    """the a an and or but of to in on for with without at by from as is are was were be been
    being it its they them their this that these those when while than then also into over more
    most less least very much many few when likely often frequently repeatedly says say said
    founder founders company companies business time thing things rather about around toward
    towards through their they're i i'll i'm we we're us our can cannot could would should
    describes describe prefers prefer enjoys enjoy tends tend often always never someone
    person people work working builds build built making make makes want wants need needs""".split()
)


@dataclass(frozen=True)
class _ArchetypeProfile:
    archetype_id: int
    code: str | None
    name: str
    core_motivation: str | None
    phrases: tuple[str, ...]
    keywords: frozenset[str]


@dataclass(frozen=True)
class ArchetypeMatch:
    archetype_id: int
    code: str | None
    name: str
    core_motivation: str | None
    score: Decimal            # 0..1 fit strength
    matched_terms: tuple[str, ...]
    is_confident: bool

    def as_founder_dna(self) -> dict:
        """Shape persisted into founder_reports.founder_dna."""
        return {
            "archetype_id": self.archetype_id,
            "archetype_code": self.code,
            "archetype_name": self.name,
            "core_motivation": self.core_motivation,
            "fit_score": float(self.score),
            "is_confident": self.is_confident,
            "matched_terms": list(self.matched_terms),
        }


class ArchetypeEngine:
    """Named engine: assign the best-fit founder archetype from answer text."""

    def __init__(
        self,
        repository: ReasoningRepository,
        *,
        min_confidence: Decimal = Decimal("0.15"),
    ):
        self.repository = repository
        self.min_confidence = min_confidence

    def assign(self, answer_texts: Sequence[str]) -> ArchetypeMatch | None:
        """Best-fit archetype for the founder, or None when there is no signal
        (no answers, or nothing in the founder's words matches any archetype)."""
        founder_blob = self._normalise(" ".join(t for t in answer_texts if t))
        founder_tokens = set(_TOKEN.findall(founder_blob))
        if not founder_tokens:
            return None

        profiles = self._profiles()
        if not profiles:
            return None

        scored: list[tuple[Decimal, int, ArchetypeMatch]] = []
        for p in profiles:
            score, matched = self._score(p, founder_tokens, founder_blob)
            scored.append(
                (
                    score,
                    p.archetype_id,
                    ArchetypeMatch(
                        archetype_id=p.archetype_id, code=p.code, name=p.name,
                        core_motivation=p.core_motivation, score=score,
                        matched_terms=matched, is_confident=False,
                    ),
                )
            )
        # Best by score desc, then lowest archetype_id (deterministic tiebreak).
        scored.sort(key=lambda t: (-t[0], t[1]))
        best_score, _, best = scored[0]
        if best_score <= 0:
            return None
        runner_up = scored[1][0] if len(scored) > 1 else Decimal("0")
        confident = best_score >= self.min_confidence and best_score > runner_up
        return ArchetypeMatch(
            archetype_id=best.archetype_id, code=best.code, name=best.name,
            core_motivation=best.core_motivation, score=best_score,
            matched_terms=best.matched_terms, is_confident=confident,
        )

    # --- Internals --------------------------------------------------------

    def _profiles(self) -> list[_ArchetypeProfile]:
        rows = self.repository.get_archetypes()
        raw: list[tuple[dict, list[str], set[str]]] = []
        doc_freq: Counter[str] = Counter()
        for row in rows:
            traits = row.key_traits or {}
            criteria = row.assignment_criteria or ""
            phrases = tuple(
                self._normalise(p) for p in _PHRASE.findall(criteria) if p.strip()
            )
            trait_text = " ".join(
                str(traits.get(k, "")) for k in ("decision_style", "stress_pattern", "core_motivation")
            )
            kw = {
                t for t in self._tokens(f"{criteria} {trait_text}")
                if len(t) >= _MIN_KEYWORD_LEN and t not in _STOPWORDS
            }
            for t in kw:
                doc_freq[t] += 1
            raw.append(
                (
                    {
                        "archetype_id": row.archetype_id,
                        "code": row.archetype_code,
                        "name": row.archetype_name,
                        "core_motivation": traits.get("core_motivation"),
                        "phrases": phrases,
                    },
                    list(kw),
                    kw,
                )
            )

        # Distinctive = not shared by half or more of the archetypes.
        cutoff = max(2, (len(rows) + 1) // 2)
        profiles: list[_ArchetypeProfile] = []
        for meta, kw_list, kw_set in raw:
            distinctive = frozenset(t for t in kw_set if doc_freq[t] < cutoff)
            profiles.append(
                _ArchetypeProfile(
                    archetype_id=meta["archetype_id"], code=meta["code"],
                    name=meta["name"], core_motivation=meta["core_motivation"],
                    phrases=meta["phrases"], keywords=distinctive,
                )
            )
        return profiles

    def _score(
        self, p: _ArchetypeProfile, founder_tokens: set[str], founder_blob: str
    ) -> tuple[Decimal, tuple[str, ...]]:
        matched: list[str] = []
        phrase_hits = 0
        for phrase in p.phrases:
            if phrase and phrase in founder_blob:
                phrase_hits += 1
                matched.append(phrase)
        keyword_hits = 0
        for kw in sorted(p.keywords):
            if kw in founder_tokens:
                keyword_hits += 1
                matched.append(kw)

        denom = _PHRASE_WEIGHT * len(p.phrases) + len(p.keywords)
        if denom == 0:
            return Decimal("0"), ()
        raw = _PHRASE_WEIGHT * phrase_hits + keyword_hits
        score = (Decimal(raw) / Decimal(denom)).quantize(_QUANT, rounding=ROUND_HALF_UP)
        return score, tuple(matched)

    def _tokens(self, text: str) -> set[str]:
        return set(_TOKEN.findall(text.lower()))

    def _normalise(self, text: str) -> str:
        # Lowercase; keep letters/digits/apostrophes so signature phrases like
        # "i'll just do it" match regardless of surrounding punctuation.
        return " ".join(re.sub(r"[^a-z0-9' ]+", " ", text.lower()).split())
