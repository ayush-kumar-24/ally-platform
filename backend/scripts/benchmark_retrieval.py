"""Benchmark pgvector similarity search over the seeded reference data.

    python scripts/benchmark_retrieval.py

Read-only: it probes with an existing row's embedding (no embedding model
needed), checks correctness, measures latency, and prints the query plan so you
can confirm the hnsw index is used rather than a sequential scan.
"""

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text  # noqa: E402

from app.db.session import SessionLocal, engine  # noqa: E402
from app.services.retrieval import similarity_search, to_vector_literal  # noqa: E402

_SEARCH = (
    "SELECT root_cause_id FROM root_causes WHERE embedding IS NOT NULL "
    "ORDER BY embedding <=> CAST(:qv AS vector) LIMIT :k"
)


def ef_search_sweep() -> None:
    """Vary hnsw.ef_search and report recall@10 vs an exact scan + latency.

    Recall is measured against ground-truth exact nearest neighbours (a forced
    sequential scan), averaged over several probes.
    """
    k = 10
    with engine.connect() as conn:
        probes = conn.execute(text(
            "SELECT embedding::text FROM root_causes WHERE embedding IS NOT NULL "
            "ORDER BY root_cause_id LIMIT 5"
        )).scalars().all()

        # ground truth: exact top-k via sequential scan (index disabled)
        conn.execute(text("SET enable_indexscan=off"))
        conn.execute(text("SET enable_bitmapscan=off"))
        exact = [
            set(conn.execute(text(_SEARCH), {"qv": p, "k": k}).scalars().all())
            for p in probes
        ]
        conn.execute(text("SET enable_indexscan=on"))
        conn.execute(text("SET enable_bitmapscan=on"))

        print(f"\nef_search sweep (root_causes, k={k}, recall vs exact, {len(probes)} probes):")
        print(f"  {'ef_search':>9} {'recall@10':>10} {'latency_ms':>11}")
        for ef in (10, 20, 40, 100, 200):
            conn.execute(text(f"SET hnsw.ef_search = {ef}"))
            recalls, times = [], []
            for i, p in enumerate(probes):
                t0 = time.perf_counter()
                got = set(conn.execute(text(_SEARCH), {"qv": p, "k": k}).scalars().all())
                times.append((time.perf_counter() - t0) * 1000)
                recalls.append(len(got & exact[i]) / k)
            conn.execute(text("RESET hnsw.ef_search"))
            print(f"  {ef:>9} {sum(recalls) / len(recalls):>10.2f} {sum(times) / len(times):>11.1f}")
        print("  (latency includes network round-trip to the remote DB; recall is the tuning signal)")


def main() -> int:
    db = SessionLocal()
    try:
        probe = db.execute(text(
            "SELECT root_cause_id, root_cause_name, embedding::text "
            "FROM root_causes WHERE embedding IS NOT NULL LIMIT 1"
        )).first()
        if probe is None:
            print("No embedded root_causes to benchmark.")
            return 1
        probe_id, probe_name, emb_text = probe
        qv = json.loads(emb_text)
        print(f"probe: root_cause_id={probe_id} '{probe_name[:50]}' | dim={len(qv)}\n")

        # 1. correctness -- a vector searched against itself should rank itself #1
        print("top-3 matches (root_causes searched with its own vector):")
        for r in similarity_search(db, "root_causes", qv, k=3):
            print(f"  id={r['id']:>4}  score={r['score']:.4f}  {str(r['label'])[:55]}")

        # 2. latency
        n = 30
        t0 = time.perf_counter()
        for _ in range(n):
            similarity_search(db, "root_causes", qv, k=5)
        avg_ms = (time.perf_counter() - t0) / n * 1000
        print(f"\nlatency: {avg_ms:.1f} ms/query avg over {n} runs "
              f"(root_causes = 807 vectors, k=5)")

        # 3. index usage
        print("\nquery plan (want an Index Scan using the hnsw index, not Seq Scan):")
        plan = db.execute(text(
            "EXPLAIN (ANALYZE, BUFFERS) "
            "SELECT root_cause_id FROM root_causes WHERE embedding IS NOT NULL "
            "ORDER BY embedding <=> CAST(:qv AS vector) LIMIT 5"
        ), {"qv": to_vector_literal(qv)}).all()
        for line in plan:
            print("  ", line[0])
    finally:
        db.close()

    ef_search_sweep()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
