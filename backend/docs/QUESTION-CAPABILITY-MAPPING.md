# Question → Capability mapping — Step 7A

The deterministic semantic bridge between the 3,340-question bank and the 34
capabilities. Seeded by migration `c5e7b1a94f60`.

**This step adds no behaviour.** `question_capabilities` is read by nothing: no
capability is scored, no gap is computed, no intervention is chosen, and
question selection is untouched. It is data that Step 7B will consume.

| | |
|---|---:|
| Total questions | 3,340 |
| **HIGH — seeded** | **1,466 (44%)** |
| MEDIUM — reported, not seeded | 1,451 candidate pairs across 51 problems |
| Unmapped | 1,874 |
| Questions mapped to 2+ capabilities | **0** |
| Problem-level decisions | 202 HIGH · 51 MEDIUM · 20 REJECT |

---

## Methodology

### Curated at the problem level, not the question level

3,340 questions hang off 273 problems, and the problem is the unit an editor
actually reasoned about. Curating **202 decisions a reviewer can read** beats
1,466 opaque pairs nobody will audit — so the migration carries the decisions
and expands them in SQL.

### Problem size turned out to be a proxy for semantic purity

The large problems were used as dumping grounds. Verified by reading them:

| Problem | Questions | What it actually contains |
|---|---:|---|
| `PRD-002` Lack of User Feedback Loop | 157 | data infrastructure, incident response, board reporting |
| `TM-006` Cultural and Communication Problems | 110 | *"When did you last take a real day off?"*, *"Is key process knowledge documented?"* |
| `FIN-001` No Ongoing Cash Flow Monitoring | 37 | budget-building questions (that is `FIN-PLAN`, not `FIN-CASH`) |

Whereas the small, precisely-named ones are uniform — every question in
`OPS-031 No Central, Accessible Place Where SOPs Are Stored` is about exactly
that.

So a problem is admitted at **HIGH** only when it names one observable practice
**and** a read of its questions showed them homogeneous.

### The admission test is the capability's own evidence criteria

Not *"is this related to"* but *"can the answer tell us this"*. That test is what
caught the clearest error in the first pass: the five **employment-policy**
problems had been mapped to `OPS-SOP`, but

> *"Have your employment practices or policies ever been reviewed by a lawyer?"*

does not evidence *"How-to knowledge is written down"*, *"Documentation is
findable"* or *"Someone absent does not stop the work"*. They were demoted — see
the taxonomy gap below.

### Founder psychology is mostly rejected

20 of the 30 `PSY-*` problems map to nothing. A trait is not a capability, and
evidence must not be inferred from consequences. The ten that survive name an
observable practice rather than a feeling — `PSY-019 No Accountability Culture
in the Team`, `PSY-011 Poor Communication When Delegating` — not because
psychology eventually affects the business.

### One capability per question

Nothing maps to two. One strong direct mapping beats several speculative ones,
and no problem earned a second.

---

## Coverage per capability

| id | capability | domain | HIGH (seeded) | MEDIUM (review) | stage split |
|---:|---|---|---:|---:|---|
| 2 | `GTM-ACQ` Repeatable Acquisition | GTM | 234 | 48 | S0→1:135 S1→10+:99 |
| 1 | `GTM-ICP` Customer & Segment Clarity | GTM | 34 | 118 | S0:18 S0→1:6 S1→10+:10 |
| 5 | `GTM-OWN` Sales Ownership Beyond the Founder | GTM | 4 | 0 | S1→10+:4 |
| 4 | `GTM-PIPE` Pipeline Visibility & Forecasting | GTM | 125 | 0 | S0→1:62 S1→10+:63 |
| 6 | `GTM-RETAIN` Retention & Expansion | GTM | 65 | 39 | S0→1:12 S1→10+:53 |
| 3 | `GTM-SALES` Repeatable Sales System | GTM | 101 | 57 | S0→1:90 S1→10+:11 |
| 8 | `FND-DELEG` Delegation & Decision Ownership | FOUNDER | 18 | 52 | S0→1:4 S1→10+:14 |
| 10 | `FND-FOCUS` Strategic Focus | FOUNDER | 11 | 39 | S0:1 S0→1:4 S1→10+:6 |
| 9 | `FND-INDEP` Operational Independence from the Founder | FOUNDER | 24 | 6 | S0→1:7 S1→10+:17 |
| 11 | `FND-LEAD` Leadership Capacity | FOUNDER | 16 | 0 | S1→10+:16 |
| 7 | `FND-TIME` Founder Time Allocation | FOUNDER | 0 **⚠ none** | 52 | — |
| 15 | `ORG-CADENCE` Management Cadence & Communication | ORG | 8 | 0 | S1→10+:8 |
| 16 | `ORG-CULTURE` Culture & Retention | ORG | 41 | 110 | S0:2 S0→1:9 S1→10+:30 |
| 13 | `ORG-HIRE` Hiring Capability | ORG | 40 | 37 | S0→1:36 S1→10+:4 |
| 14 | `ORG-PERF` Performance & Accountability | ORG | 53 | 0 | S0:1 S0→1:44 S1→10+:8 |
| 12 | `ORG-ROLES` Role Clarity & Ownership | ORG | 14 | 54 | S0→1:6 S1→10+:8 |
| 20 | `OPS-MONITOR` Operational Monitoring | OPS | 13 | 0 | S1→10+:13 |
| 17 | `OPS-PROCESS` Repeatable Processes | OPS | 8 | 26 | S1→10+:8 |
| 19 | `OPS-QUALITY` Quality Control | OPS | 18 | 0 | S0→1:8 S1→10+:10 |
| 18 | `OPS-SOP` Documentation & SOPs | OPS | 43 | 0 | S0→1:35 S1→10+:8 |
| 21 | `OPS-TOOLING` Systems & Tooling | OPS | 0 **⚠ none** | 121 | — |
| 24 | `FIN-CASH` Cash & Runway Planning | FIN | 72 | 74 | S0→1:36 S1→10+:36 |
| 26 | `FIN-INVEST` Investor Readiness | FIN | 79 | 26 | S0→1:20 S1→10+:59 |
| 25 | `FIN-PLAN` Financial Planning & Budgeting | FIN | 73 | 0 | S0→1:65 S1→10+:8 |
| 23 | `FIN-UNIT` Unit Economics | FIN | 48 | 24 | S0→1:40 S1→10+:8 |
| 22 | `FIN-VIS` Financial Visibility | FIN | 84 | 30 | S0:4 S0→1:71 S1→10+:9 |
| 28 | `PRD-DELIVERY` Delivery Predictability | PROD | 0 **⚠ none** | 0 | — |
| 27 | `PRD-DISCOVER` Customer Discovery & Validation | PROD | 18 | 96 | S0:18 |
| 29 | `PRD-FEEDBACK` Feedback Loops | PROD | 10 | 157 | S0:10 |
| 30 | `PRD-ROADMAP` Roadmap & Prioritisation Discipline | PROD | 0 **⚠ none** | 188 | — |
| 33 | `STR-COMPETE` Competitive Awareness | STRAT | 58 | 37 | S0:19 S0→1:10 S1→10+:29 |
| 32 | `STR-MODEL` Business Model Design | STRAT | 50 | 4 | S0:12 S0→1:24 S1→10+:14 |
| 34 | `STR-PLAN` Planning & Goal Setting | STRAT | 82 | 56 | S0:36 S0→1:26 S1→10+:20 |
| 31 | `STR-POSITION` Positioning & Differentiation | STRAT | 22 | 0 | S1→10+:22 |

---

## Capabilities with no questions — 4 of 34

A capability nobody can ask about can never be assessed, so it can never become
a gap. These are tracked by `test_capabilities_without_questions_are_known_and_few`,
which fails if the set changes — so the gap cannot silently stop being tracked.

| Capability | Why | Route |
|---|---|---|
| `PRD-DELIVERY` Delivery Predictability | **no question in the bank asks it**, at HIGH or MEDIUM. A genuine content gap | needs new questions |
| `PRD-ROADMAP` Roadmap & Prioritisation Discipline | 188 MEDIUM candidates, all inside the heterogeneous `PRD-001/003/005` | needs question-level curation |
| `OPS-TOOLING` Systems & Tooling | 121 MEDIUM, from the three `*-15x`/`TM-077` "no tooling" problems (30 questions each, too large to certify) | needs question-level curation |
| `FND-TIME` Founder Time Allocation | 52 MEDIUM, all in `PSY-027 No Deliberate Daily Operating Habits` — a sample read clean, but 52 questions cannot be certified from 5 | needs question-level curation |

Also thin: **`GTM-OWN` Sales Ownership Beyond the Founder has 4 questions**, from
`SCL-020` alone. This is the same content gap Step 5 flagged in the intervention
library — the bank is strong on the founder selling better and near-silent on
handing sales to someone else, which is the capability a ₹1 Cr → ₹10 Cr founder
most needs.

---

## Taxonomy gap: Compliance & Governance

Six problems — `OPS-006`, `OPS-026`, `OPS-051`, `OPS-056`, `OPS-061`, `OPS-066`,
`RSK-016` — are about employment policy, legal review, data privacy and
governance. **No capability in the 34 has a criterion any of them can inform.**

They are left unmapped rather than forced into `OPS-SOP` (documentation) or
`STR-PLAN` (planning), both of which would be a category error. Either the
taxonomy needs a seventh `OPS` capability, or these questions stay outside the
capability model permanently — a product decision, not a curation one.

---

## MEDIUM — reported for review, deliberately not seeded

A false mapping contaminates every future capability assessment, and it does so
invisibly: the founder is told something about a capability nobody actually
asked them about. These need question-level curation before they can be seeded.

| Problem | Name | Questions | Candidate |
|---|---|---:|---|
| `BPL-002` | Goals Not Broken Down into Actionable Milestones | 32 | `STR-PLAN` |
| `FIN-001` | No Ongoing Cash Flow Monitoring Process | 37 | `FIN-CASH` |
| `FIN-006` | No Ongoing Runway Forecasting Discipline | 37 | `FIN-CASH` |
| `FIN-152` | No Real Financial Oversight Capability | 30 | `FIN-VIS` |
| `FIN-153` | No Financial Systems or Tracking Tools | 30 | `OPS-TOOLING` |
| `FND-006` | Poor Fundraising Timing | 26 | `FIN-INVEST` |
| `GTM-001` | Confusing GTM with Marketing | 11 | `GTM-ACQ` |
| `GTM-002` | Undefined ICP or Broad Targeting | 118 | `GTM-ICP` |
| `GTM-005` | Neglecting Pricing Strategy | 24 | `FIN-UNIT` |
| `IVA-001` | No Real Market Need or Validation | 37 | `PRD-DISCOVER` |
| `IVA-002` | Overly Niche or Derivative Idea | 56 | — |
| `IVA-005` | Failure to Pivot | 10 | — |
| `IVA-007` | Building Before Problem Framing | 59 | `PRD-DISCOVER` |
| `MEX-011` | No Structured Process for Planning Marketing Campaigns | 37 | `GTM-ACQ` |
| `MEX-102` | No Dedicated Marketing Capability | 30 | — |
| `MEX-103` | No Marketing Tools or Performance Tracking | 30 | `OPS-TOOLING` |
| `OPE-001` | No Framework Used to Evaluate New Opportunities | 24 | `STR-PLAN` |
| `OPE-002` | No Process for Saying No to Distracting Opportunities | 39 | `FND-FOCUS` |
| `OPS-001` | No Processes or Ad-Hoc Operations | 26 | `OPS-PROCESS` |
| `OPS-003` | Scaling Prematurely Without Operational Stability | 13 | — |
| `OPS-006` | Neglecting Compliance and Governance | 11 | — |
| `OPS-026` | No Company Policies or Employment Documentation | 7 | — |
| `OPS-051` | No Consistent Enforcement of Existing Policies | 7 | — |
| `OPS-056` | No Process for Employees to Formally Acknowledge or Sign Off on Policies | 7 | — |
| `OPS-061` | No Coverage of High-Risk Policy Areas Like Conduct, Harassment, or Data Privacy | 7 | — |
| `OPS-066` | No Process for Reviewing and Updating Policies as Laws or the Business Change | 7 | — |
| `PRD-001` | Building Unwanted Features | 54 | `PRD-ROADMAP` |
| `PRD-002` | Lack of User Feedback Loop | 157 | `PRD-FEEDBACK` |
| `PRD-003` | Over-Engineering and Perfectionism | 66 | `PRD-ROADMAP` |
| `PRD-005` | No Clear Product Vision | 60 | `PRD-ROADMAP` |
| `PRD-006` | Sacrificing User Needs for Quick Monetization | 11 | — |
| `PRD-007` | Product Mis-Timing | 23 | — |
| `PSY-005` | Hero Syndrome — Refusing to Delegate or Share Load | 13 | `FND-DELEG` |
| `PSY-008` | Weak Delegation Ability | 39 | `FND-DELEG` |
| `PSY-009` | Perfectionism Creating Invisible Bottlenecks | 6 | `FND-INDEP` |
| `PSY-027` | No Deliberate Daily Operating Habits | 52 | `FND-TIME` |
| `RSK-016` | No Legal or Compliance Risk Review Ever Done | 6 | — |
| `SAL-002` | Inability to Close Deals | 57 | `GTM-SALES` |
| `SAL-005` | Over-Discounting and High Customer Churn | 39 | `GTM-RETAIN` |
| `SCL-027` | Compensation and Equity Complexity | 4 | — |
| `SCL-038` | Innovation Pressure vs Execution Focus | 4 | `PRD-ROADMAP` |
| `SCL-042` | International Expansion Complexity | 4 | `STR-MODEL` |
| `SCL-049` | Balancing Innovation with Operational Structure | 4 | `PRD-ROADMAP` |
| `SLX-131` | No Competitive Intelligence Gathered From Lost Deals | 37 | `STR-COMPETE` |
| `SLX-196` | No Sales Tooling or Pipeline Visibility | 30 | `OPS-TOOLING` |
| `TM-001` | Co-founder Conflicts | 16 | — |
| `TM-002` | Wrong or Weak Team Composition | 42 | `ORG-ROLES` |
| `TM-004` | Poor Hiring Practices | 37 | `ORG-HIRE` |
| `TM-005` | Weak Governance or Oversight | 12 | `ORG-ROLES` |
| `TM-006` | Cultural and Communication Problems | 110 | `ORG-CULTURE` |
| `TM-077` | No People Systems or HR Tooling | 31 | `OPS-TOOLING` |
