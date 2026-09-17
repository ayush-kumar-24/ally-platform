"""Curated directed `explains` relationships between problems.

DISTINCT FROM `problems.related_problem_ids`, which is association and is left
untouched. "A is related to B" is symmetric and says nothing about which one
accounts for the other; "A explains B" is directed and is the claim ranking
needs in order to tell a root cause from a symptom.

WHY THIS IS A PYTHON MODULE AND NOT A TABLE

A first version needs no migration. The edges are domain knowledge about a fixed
catalogue, not per-founder state: they change when someone revises the problem
taxonomy, which is a code change, not a runtime write. A table becomes worth it
when the set is large enough to want editing outside a deploy, and it is not
close to that yet -- see the note on coverage below.

HOW THESE EDGES WERE CHOSEN, AND WHY THERE ARE SO FEW

Only where the problem definitions themselves carry the claim. Searching all 273
descriptions for explicit causal language -- "downstream consequence", "stems
from", "caused by", "result of failing" -- returns exactly ONE problem. The
taxonomy is written as a catalogue of independent problems, not as a causal
model, so an honest reading of it supports very few directed edges.

The temptation here is obvious and was declined: adding GTM-002 -> SAL-002 would
make the ComplyFlow QA persona rank the way its ground truth says it should.
The taxonomy does not support it. SAL-002 is defined as a capability gap --
"founders ... lack the specialized skills required to run discovery, handle
objections" -- and is explicitly compounded by missing feedback loops, not by
undefined targeting. Writing that edge would be encoding a test's expected
answer as domain knowledge.

So: two edges, both defensible from the text, neither chosen for its effect on a
persona. Growing this set is a content exercise for someone with authority over
the taxonomy, not something to infer.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class ExplanatoryLink:
    """`source` accounts, in part, for `target`.

    `strength` is how well the taxonomy supports the claim, not how strongly a
    given founder's evidence does -- the evidence half is the ranker's job. It
    is deliberately coarse: these are curated judgements, and a third decimal
    place would imply a precision nobody measured.
    """

    source: str          # problem_code
    target: str          # problem_code
    strength: Decimal    # 0..1, support in the taxonomy
    rationale: str       # why this is explanatory and not merely related


#: The curated set. Small on purpose; see the module docstring.
EXPLAINS: tuple[ExplanatoryLink, ...] = (
    ExplanatoryLink(
        source="GTM-002",
        target="SAL-001",
        strength=Decimal("0.9"),
        rationale=(
            "SAL-001's own description states it: 'This empty pipeline is a "
            "direct downstream consequence of failing to define the target "
            "buyer or the specific sales motion.' GTM-002 IS failing to define "
            "the target buyer. The taxonomy asserts the direction itself."
        ),
    ),
    ExplanatoryLink(
        source="GTM-002",
        target="GTM-004",
        strength=Decimal("0.7"),
        rationale=(
            "GTM-004 is defined as copy that fails to explain how the product "
            "solves a specific problem 'for a specific user'. Positioning is "
            "written against a defined user, so an undefined ICP removes the "
            "input positioning requires. Weaker than GTM-002 -> SAL-001 because "
            "the dependency is implied by the definition rather than stated."
        ),
    ),
)


def _validate(links: tuple[ExplanatoryLink, ...]) -> None:
    """Reject a cyclic or self-referential edge set at import.

    Coverage is computed over direct edges only, so a cycle cannot currently
    inflate a score. It is rejected anyway: the moment anyone adds multi-hop
    reasoning, a cycle that was already in the data becomes an unbounded loop,
    and the cheapest place to stop that is before it is ever written down.
    """
    seen: set[tuple[str, str]] = set()
    adjacency: dict[str, set[str]] = {}
    for link in links:
        if link.source == link.target:
            raise ValueError(f"explanatory link explains itself: {link.source}")
        if (link.source, link.target) in seen:
            raise ValueError(
                f"duplicate explanatory link: {link.source} -> {link.target}")
        seen.add((link.source, link.target))
        adjacency.setdefault(link.source, set()).add(link.target)

    # Depth-first cycle check. The set is tiny; clarity beats cleverness.
    visiting: set[str] = set()
    done: set[str] = set()

    def walk(node: str, path: list[str]) -> None:
        if node in visiting:
            cycle = " -> ".join(path + [node])
            raise ValueError(f"explanatory links form a cycle: {cycle}")
        if node in done:
            return
        visiting.add(node)
        for nxt in adjacency.get(node, ()):
            walk(nxt, path + [node])
        visiting.discard(node)
        done.add(node)

    for source in adjacency:
        walk(source, [])


_validate(EXPLAINS)


def explanatory_coverage(
    source_problem: str | None,
    observed_problems: set[str],
    links: tuple[ExplanatoryLink, ...] = EXPLAINS,
) -> Decimal:
    """How much of what we actually observed this problem accounts for, 0..1.

    DIRECT EDGES ONLY, and only to problems observed in THIS session. Both
    restrictions are deliberate:

      * no multi-hop and no centrality -- a problem does not become a better
        explanation because the catalogue happens to be densely connected
        around it, and the earlier investigation showed degree centrality over
        `related_problem_ids` promoting whichever candidate sat in the busiest
        neighbourhood;
      * only observed targets -- explaining a problem this founder does not
        have is not evidence about this founder.

    Saturating in the number of targets explained, so a second explained
    problem counts for much more than a fifth, and strengths cap the total. A
    source explaining nothing observed scores 0, which is the common case while
    the curated set is this small.
    """
    if not source_problem or source_problem not in observed_problems:
        return Decimal("0")
    hits = [
        link.strength
        for link in links
        if link.source == source_problem
        and link.target in observed_problems
        and link.target != source_problem
    ]
    if not hits:
        return Decimal("0")
    # Diminishing returns: 1 - product(1 - strength). Two independent edges of
    # 0.9 and 0.7 give 0.97, never more than 1, and a weak edge cannot be
    # stacked into certainty.
    remaining = Decimal("1")
    for strength in hits:
        remaining *= (Decimal("1") - max(Decimal("0"), min(Decimal("1"), strength)))
    return Decimal("1") - remaining
