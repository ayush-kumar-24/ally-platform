# Retrieval (pgvector) — benchmark & tuning notes

Reproduce with: `python scripts/benchmark_retrieval.py`

Measured against the live seeded data (`root_causes`, 807 embedded vectors,
`vector(384)`, cosine / hnsw index `idx_root_causes_embedding`).

## 1. Correctness — semantic search works

Searching `root_causes` with an existing row's own vector returns itself first,
then genuinely related concepts:

```
id=517  score=1.0000  Identity Fusion      (itself)
id= 44  score=0.9587  Identity Fusion      (related)
id=568  score=0.9198  Founder Identity     (related)
```

## 2. Index is used (not a sequential scan)

`EXPLAIN (ANALYZE)` on the top-k query:

```
Index Scan using idx_root_causes_embedding on root_causes
Execution Time: 0.42 ms
```

Sub-millisecond, index-backed. The ~65–90 ms seen from the benchmark script is
**network round-trip** to the remote Supabase (ap-south-1) from a dev laptop —
in production, with the backend near the DB, real latency ≈ the 0.42 ms.

## 3. `ef_search` sweep — recall vs the tuning knob

`hnsw.ef_search` trades recall for speed. Recall@10 measured against an exact
(sequential-scan) top-10, averaged over 5 probes:

| ef_search | recall@10 |
|-----------|-----------|
| 10        | 1.00 |
| 20        | 1.00 |
| 40 (default) | 1.00 |
| 100       | 1.00 |
| 200       | 1.00 |

## Conclusion / tuning proposal

**No tuning needed at the current scale.** Even the lowest `ef_search` returns
perfect recall — expected, because the datasets are small (hundreds to low
thousands of vectors). The default `ef_search = 40` and the existing hnsw indexes
are correct as-is; do **not** add indexes or change settings now.

**Revisit only if a table grows large** (roughly 10k+ vectors — most likely
`rag_chunks` once RAG documents are ingested). At that point:
- re-run this sweep on that table,
- if recall drops, raise `hnsw.ef_search` (recall↑, latency↑),
- consider `hnsw (m, ef_construction)` build params for very large sets.

The `similarity_search` helper (`app/services/retrieval.py`) already uses the
cosine operator that matches the index, so it benefits from all of the above.
