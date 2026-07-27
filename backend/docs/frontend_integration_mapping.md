# Frontend ↔ Backend integration mapping

Status: **no integration yet.** The React frontend (`ally-platform/frontend`) is a
prototype with zero API calls — every screen renders hardcoded local data. This
doc is the blueprint for wiring it up: what maps to what, where the vocabulary is
now settled, and the two things blocked on a product decision.

Decisions captured here were made 2026-07-27. Where frontend and backend
disagree, **backend wins** (it has the seeded data and drives the engine).

---

## 0. Canonical option lists — consume these, stop hardcoding

New reference API (built 2026-07-27) serves the backend-owned pickers. The
frontend should render dropdowns from these instead of its own values:

| Endpoint | Returns |
|---|---|
| `GET /api/v1/reference/stages` | 8 stages, flat + grouped by the 2-tier label |
| `GET /api/v1/reference/industries` | the 4 seeded industries |
| `GET /api/v1/reference/business-pillars` | the 6 readiness pillars (Business-DNA dims) |

---

## 1. Stage — frontend 4 labels → backend 8 stages

Backend wins, no contest: the 8-stage model drives question filtering,
`root_cause_weights`, and tone selection. Replace the frontend's flat 4-option
picker (`Idea / Early traction / Scaling / Plateau`) with the **2-tier picker**
(group → specific stage), served by `/reference/stages`.

The 8 stages group into 3 tiers via `onboarding_label`:

| Tier (`onboarding_label`) | Stages (`stage_id`) |
|---|---|
| Stage 0 | Ideation (1) |
| Stage 0→1 | Validation (2), Prototype/MVP (3), Early Traction (4) |
| Stage 1→10+ | Growth/Scaling (5), Expansion (6), Maturity (7), Exit (8) |

Rough remap of the old prototype labels (for migrating any existing mock copy —
the real UI should use the 2-tier picker, not this):

| Frontend label | → backend stage |
|---|---|
| Idea | Ideation (1) |
| Early traction | Early Traction (4) |
| Scaling | Growth / Scaling (5) |
| **Plateau** | **no stage** — see below |
| `MOCK_FOUNDER.stage = "Seed"` | funding term, not a stage — drop |

**"Plateau" orphan:** a real founder experience but a *condition*, not a stage.
Do not force it into a stage and do not silently delete it. Capture it elsewhere
(e.g. a founder-state/mood field) if product wants it. **[product decision]**

Note: the profile `/business` endpoint already accepts a stage **name** and
resolves it to `stage_id`, so the frontend sends the chosen `stage_name`.

---

## 2. Industry — frontend 7 → backend 4

Backend's 4 win — they have seeded `stage_thresholds_inr` + pain-point weights;
the frontend's extra options do not. Do **not** offer industries the engine can't
differentiate (false promise). Mapping is anchored in each industry's seeded
subtitle:

| Frontend option | → backend industry (`industry_id`) | Why |
|---|---|---|
| SaaS / B2B | Technology & SaaS (1) | direct |
| AI / ML | Technology & SaaS (1) | subtitle lists "AI platforms" |
| Marketplace | Technology & SaaS (1) | subtitle lists "marketplace platforms" |
| Fintech | Technology & SaaS (1) | software product |
| Healthtech | Technology & SaaS (1) | software product |
| D2C / Consumer | Manufacturing & D2C (3) | subtitle lists "physical product brands, FMCG…" |
| Services | Services & Consulting (2) | direct |
| _(missing)_ | Social Impact & NGO (4) | **add to the frontend picker** — backend has it, frontend doesn't |

Add real new verticals (a true Fintech/Healthtech row) only when someone seeds
their thresholds + pain-point weights. **[future data work]**

---

## 3. Business dimensions — frontend's 3 sets → 6 readiness pillars

The frontend has three competing sets (BusinessDNA.jsx = 8, Report.jsx = 4,
Dashboard = 6); none matches the backend. Collapse all to the **6 pillars**
(`/reference/business-pillars`), which have weightages summing to 100, score
bands, red-flag thresholds and a working questions→pillar chain:

Founder Readiness (25) · Market Clarity (20) · Revenue Maturity (20) ·
Product & Execution (15) · Team & Leadership (10) · Strategic Clarity (10).

Business-health scoring is seeded backend-side (`PILLAR_SCORE_FROM_ANSWERS`,
`BUSINESS_HEALTH_SCORE_FORMULA`), so per-pillar scores (0–100, already
health-oriented) will be real once the engine runs.

---

## 4. Onboarding (13 DNA fields) — already backend-mapped

The guided onboarding (`ProfileBuild.jsx` / `Summary.jsx`) collects 13 fields
that map to the `/profile` section endpoints (not `founder_context`). Keys:
`stage, building, problem, customer, industry, challenges, goal90, vision, why,
working, experience, feeling, reflection`. `stage` and `industry` must use the
canonical lists above; `feeling` must map display labels → the 8 stored
`emotional_state` values (jsonb multi-select).

`founder_context` (#12: geographic_type, economic_background, education_level,
industry_exposure, language_comfort, network_access) has **no frontend screen
yet** — either add one or leave those fields unset.

---

## 5. Report / intelligence — where a backend source exists

Report screens (`Report.jsx` / `GuidedReport.jsx`) render a rich structure.
Backend source per section (via `founder_reports` + `detected_root_causes`, read
through the `/api/v1/intelligence/*` APIs built 2026-07-27):

| Frontend field | Backend source | Notes |
|---|---|---|
| overall clarity score `74` | `sessions.overall_confidence_score` | 0–100 already ✓; post-session only |
| business dimension scores | 6 pillar scores | 0–100, health-oriented |
| founder DNA dimension scores | **none** | see Blocked #1 |
| root-cause name/category | `intelligence` top_root_causes | ids resolved to labels |
| root-cause confidence `92%` | `detected_root_causes.final_weighted_score` | **0–1 → ×100** for display |
| `ACTIONS {num,text,tag,tagLabel}` | `founder_reports.confirm_actions` / `solve_actions` | map priority→tag, next_actions[0]→text |
| `EVIDENCE {val,desc}` | **none** | see Blocked #2 |
| `ROADMAP {kicker,days,items}` | **none** | see Blocked #2 |
| `WHY_STEPS {bold,text}` | **none** | see Blocked #2 |

**Score scale:** frontend renders everything as 0–100 %. `overall_confidence`
is already 0–100; root-cause / category scores are 0–1 and need ×100.

**A report adapter is still needed** to reshape the backend payload into the
frontend report structure — but do not build it until the blocked items below are
decided (adapting to them = building them).

---

## 6. Confidence must NOT be shown mid-session

`DiagnosisChat.jsx` and `Reveal.jsx` show a confidence % during the conversation
(84/91, a `ConfBar`). This violates the backend rule **and** Viraj's stated
principle ("scores read as grades, which we deliberately avoid"). **The frontend
changes, not the rule** — remove the in-session percentages. Aggregate confidence
in the *post-session* report is fine.

---

## Blocked — needs a product/Viraj decision before building

**1. Founder DNA (7 dimensions).** `founder_dimensions` and
`founder_dimension_profile` were dropped (2026-07-27); scoring is now
prompt-driven with no table. The frontend's 7 Founder-DNA cards have nothing to
bind to. **Decision needed:** does anything persist per founder for these (a new
store), or does the report render them transiently from the prompt output?

**2. Report roadmap / why-steps / evidence strings.** These sections
(NOW/NEXT/LATER roadmap, "why" narrative steps, evidence display strings like
"-38%"/"11 days") have no backend source. **Decision needed:** real features or
prototype decoration? Building them is net-new backend work, not a mapping.

---

## The one-pager for Viraj

1. **Confidence in the UI** — confirm the mid-session confidence % comes out of
   `DiagnosisChat`/`Reveal` (aligns the UI with "no scores shown as grades").
2. **Founder DNA** — with the rubric tables gone and scoring prompt-driven, what
   should persist per founder for the 7 Founder-DNA dimensions, if anything?
3. **Report sections** — are roadmap, why-steps, and evidence strings real report
   features (build them) or prototype decoration (drop them from the report)?
