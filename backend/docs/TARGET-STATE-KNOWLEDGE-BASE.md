# Target-State Knowledge Base — Step 6

The deterministic layer that answers one question:

> For this founder's context and intended destination, which capabilities are
> required, at what level, and why?

Seeded by migration `a8d34f7e2b91`. **55 requirement rows, 2 profile columns,
1 resolver.** Nothing here looks at a single answer the founder gave.

---

## What this step is *not*

There is no comparison with evidence, no `MISSING`, no `GAP`, no readiness
verdict. A requirement is a statement about the **destination**. Whether the
founder has the capability is Step 7; the comparison is Step 8.

`resolve_requirements(rows, founder_context, target)` has no parameter through
which evidence could arrive, and `RequiredCapability` has no field in which an
observation could be stored — both pinned by
`test_resolution_never_looks_at_an_answer`. **No evidence, no claim of a gap**
is a property of the signatures, not a promise in prose.

---

## Target context

Two nullable columns on `founders`. Profile context, never diagnostic evidence.

### `target_revenue_band`

| Value | |
|---|---|
| `under_1L` `1L_5L` `5L_25L` `25L_1Cr` | identical to `current_revenue`'s names |
| `1Cr_5Cr` `5Cr_25Cr` `above_25Cr` | the extension |

**This is deliberately not `CurrentRevenue`, and that is a conflict with
`FUTURE-STATE-DIAGNOSIS.md` §5**, which said the target should match the
existing vocabulary. It cannot: `founders_current_revenue_check` tops out at
`above_1Cr`, so a ₹1.5 Cr destination and a ₹10 Cr destination would be the same
band — and selecting different requirements for those two founders is the
column's only job.

The lower four names are shared so both vocabularies sit on one ordered ladder
(`REVENUE_LADDER` in `app/schemas/founder.py`), which is what will let Step 7+
say how far away a destination is. `pre_revenue` is absent: nobody targets it.
`current_revenue` is untouched.

### `target_time_horizon`

`6_months` · `12_months` · `24_months` · `36_months_plus`

No prior convention existed. Coarse on purpose, so the answer can be honest. It
carries **no severity** — a six-month horizon is not a worse diagnosis than a
two-year one, it selects different requirements (six months is not long enough
to build founder independence from scratch, so it must already be close to
true).

---

## `capability_requirements`

```
requirement_id, capability_id → capabilities

-- context predicate, every dimension nullable, NULL = WILDCARD
industry_code, business_model, from_stage_order,
target_revenue_band, target_time_horizon

-- what is required
required_level   smallint 0-3   CHECK, and it is CapabilityLevel from Step 5
necessity        core | contextual   CHECK
rationale        NOT NULL
source_document, created_at, updated_at
```

Two constraints worth naming:

- **`required_level` is not a new enum.** It is `CapabilityLevel` (0 absent,
  1 personal, 2 documented, 3 owned) constrained at the database so a bad row
  cannot reach the resolver.
- **`UNIQUE … NULLS NOT DISTINCT`** on the whole predicate. Two rows with the
  *same* context are a curation mistake, so the database refuses them. This is
  what keeps the resolver's ambiguity error for genuinely *different* predicates
  of equal weight.

`from_stage_order` is an inclusive **lower bound**, not an equality — so the
table needs no row per stage.

---

## The specificity cascade

For each capability, among rows whose every non-NULL dimension matches:

1. **highest specificity** — the count of non-NULL dimensions
2. **then highest `from_stage_order`** — the tightest lower bound; the only
   tie-break, because any other would be a preference dressed up as a rule
3. still tied and the requirements **differ** → `AmbiguousRequirementError`

Rule 3 raises rather than picks. Two equally-weighted rules that disagree are a
curation error, and choosing one silently would make a founder's requirements
depend on insertion order. Identical requirements from different predicates are
harmless and resolve normally.

Resolution happens in **Python, not SQL** — the table is small curated reference
data, and a rule that has to explain itself belongs next to the code that
explains it.

### Unknown context narrows nothing

A non-NULL dimension is satisfied only when the founder's value is **known and
matching**. So unknown context can never activate a specific rule, and never
removes a wildcard one:

| Context | Requirements |
|---|---|
| `saas` × `B2B` × stage 5 → `1Cr_5Cr` / `12_months` | **12** (3 overrides fire) |
| everything unknown → `1Cr_5Cr` | **10** (all wildcards kept, no specific rule) |

An incomplete profile yields a **more generic** requirement set — never an empty
one, never one nobody established. This is Step 4's *UNKNOWN is not NO* applied
to the knowledge base.

---

## Seeded requirements — 55 rows

Organised by destination, because what a business needs follows from where it is
going.

| Target band | Rows | Shape |
|---|---:|---|
| `25L_1Cr` | 6 | reaching the first crore — the founder can still be the seller, but the process must exist outside their head |
| `1Cr_5Cr` | 17 | the business must start working without the founder; `FND-DELEG`, `OPS-PROCESS`, `FIN-CASH` all become core |
| `5Cr_25Cr` | 23 | founder *replacement*, not founder improvement — `GTM-OWN` at level 3 is the single most common blocker |
| `above_25Cr` | 8 | an organisation, not a founder with help |

Plus modifiers that exist to exercise *and prove* the cascade:

- **business model** — B2B → `GTM-PIPE` 3 (long cycles); B2C → `GTM-ACQ` 3 and
  `GTM-RETAIN` 2 (repeat purchase is the economics)
- **industry** — `saas` → `GTM-RETAIN` 3 (retention *is* the model);
  `ecommerce_d2c` → `FIN-UNIT` 3; `fintech` → `FIN-VIS` 3 (external scrutiny)
- **horizon** — `5Cr_25Cr` + `6_months` → `FND-INDEP` 3, `OPS-SOP` 3
- **stage** — from Validation onward, `PRD-DISCOVER` stays load-bearing
- **combined** — `saas` × `B2C` × `1Cr_5Cr` → `GTM-RETAIN` 3, stated explicitly
  because both the industry and the business-model rule fire and disagree
  (see below)

### A collision the tests caught

`test_the_seeded_knowledge_base_resolves_without_ambiguity` sweeps **8,820
contexts** against the live rows. It found a real bug in this seed: a **SaaS
B2C** founder targeting `1Cr_5Cr` matched the `saas` rule (level 3) and the
`B2C` rule (level 2) at equal specificity. The fix was the one the error message
asks for — state the combined case explicitly — not a tie-break rule invented to
paper over it.

That sweep is what makes the table safe to extend: a new rule that collides with
an existing one fails in CI rather than in front of a founder.

---

## Intentionally unseeded

| Area | Why |
|---|---|
| 28 of 30 industries | Only `saas`, `fintech`, `ecommerce_d2c` have a defensible modifier today. The rest fall through to the wildcard rules, which is correct, not missing |
| `under_1L` · `1L_5L` · `5L_25L` bands | Nothing below ₹25L/month has a capability requirement anyone can defend — at that size the answer is "find customers", which the current-state diagnosis already handles |
| `24_months` / `36_months_plus` horizons | A long horizon means capabilities can be *built*, so they do not change what is required. Only short horizons tighten requirements |
| `B2B2C`, `marketplace`, `D2C`, `other` | No defensible modifier yet |
| Most `PROD` and `ORG` capabilities below `5Cr_25Cr` | Genuinely context-dependent below that size |

The full cross product is 30 × 6 × 8 × 7 × 4 = **40,320 contexts**. A row nobody
can defend is worse than no row: the wildcard always applies.

---

## Reference data, never generated

`capability_requirements` is dumped by `scripts/dump_reference_data.py` and
reviewed like the question bank. Nothing generates a row at runtime and nothing
may — letting an LLM invent requirements would make the destination's demands
depend on a sampling temperature, and a founder could not be shown why.
