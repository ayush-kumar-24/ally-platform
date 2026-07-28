# Indexing strategy & query performance — read/aggregation layer

Covers the founder-scoped read/aggregation queries added for the Founder
Intelligence APIs (#13), the Business-Health dashboard (#8) and Founder Memory
(#12). Vector/RAG performance is covered separately in `retrieval_benchmark.md`.

Baseline captured against the live DB on 2026-07-27. The tables are pre-data
(0 founders), so **absolute timings are not meaningful yet — the deliverable here
is index COVERAGE + access paths**, verified against `pg_indexes` and
`EXPLAIN ANALYZE`. Re-run the timings once production data exists.

---

## 1. Strategy

Every one of these queries is **founder-scoped** — it filters by `founder_id`
first, and the working set per founder is small (a handful of sessions, reports
and detections). So the strategy is simple and already satisfied:

1. A btree index on `founder_id` on **every** table these queries hit.
2. **Partial** indexes for the hot secondary filters (`is_top_finding`,
   `status = 'active'`, `status = 'approved'`) so those predicates are index-only.
3. No composite/covering indexes added yet — per-founder cardinality is low enough
   that the `founder_id` index + a cheap in-memory sort/aggregate is optimal. Revisit
   only if a single founder accumulates thousands of rows (see §4).

## 2. Index coverage (query → index)

| Query (repository method) | Table | Filter / order | Index used |
|---|---|---|---|
| `list_reports`, `get_latest_active_report` | `founder_reports` | `founder_id` (+ `is_active`), order `generated_at desc` | `idx_founder_reports_founder` |
| `list_detections` | `detected_root_causes` | `founder_id` (+ `session_id`, `is_top_finding`) | `idx_detected_rc_founder`, `idx_detected_rc_session`, `idx_detected_rc_top` (partial) |
| `recurring_root_causes` (GROUP BY) | `detected_root_causes` | `founder_id`, group by `root_cause_id` | `idx_detected_rc_founder` |
| `confidence_trend`, `completed_session_count`, `distress_session_count` | `sessions` | `founder_id` (+ `status`) | `idx_sessions_founder`, `idx_sessions_status` |
| `dashboard /business-health` | `founder_reports` | `founder_id` + `is_active` (latest) | `idx_founder_reports_founder` |
| memory `list_for_founder` | `founder_memory` | `founder_id` (+ `status='active'`) | `idx_founder_memory_founder`, `idx_founder_memory_active` (partial) |
| memory events `list_for_*` | `founder_memory_events` | `founder_id` / `memory_id` | `idx_founder_memory_events_founder`, `idx_founder_memory_events_memory` |

All indexes verified present via `pg_indexes` (2026-07-27).

## 3. Sample plan — the heaviest query (recurring root causes)

`EXPLAIN (ANALYZE, BUFFERS)` on the per-founder GROUP BY aggregate:

```
Limit  (actual time=0.125..0.126 rows=0)
  ->  Sort  (Sort Key: count(*) DESC, max(final_weighted_score) DESC)
        ->  GroupAggregate  (Group Key: root_cause_id)
              ->  Sort  (Sort Key: root_cause_id)
                    ->  Bitmap Heap Scan on detected_root_causes
                          Recheck Cond: (founder_id = 1)
                          ->  Bitmap Index Scan on idx_detected_rc_founder
                                Index Cond: (founder_id = 1)
Planning Time: 2.749 ms
Execution Time: 0.285 ms
```

The founder filter is served by **`idx_detected_rc_founder`** (Bitmap Index Scan) —
not a sequential scan — then a small group-aggregate + sort. This is the intended
access path; it holds as data grows because the scan is bounded to one founder's rows.

## 4. Recommendations

- **No new indexes required now.** Coverage is complete for the current queries.
- **If a founder accumulates many reports** and `list_reports` ordering by
  `generated_at` becomes hot, add a composite `(founder_id, generated_at DESC)` on
  `founder_reports` to make the top-N index-ordered (avoids the sort). Not worth it
  at current scale.
- **Re-run timings with production data** (this baseline is on empty tables). The
  access paths won't change; only absolute times will, and they stay bounded to
  per-founder row counts.
- The vector path (retrieval / RAG) is benchmarked separately in
  `retrieval_benchmark.md` (HNSW `ef_search` sweep) — unaffected by this layer.

## How to reproduce

```sql
explain (analyze, buffers)
select root_cause_id, count(*) occ,
       sum(case when is_top_finding then 1 else 0 end) top,
       max(final_weighted_score) best
from detected_root_causes
where founder_id = :fid
group by root_cause_id order by occ desc, best desc limit 10;
```
Swap in the other queries from §2; confirm each shows an `Index Scan` /
`Bitmap Index Scan` on the `founder_id` index rather than a `Seq Scan`.
