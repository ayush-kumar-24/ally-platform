# Capability taxonomy — Step 5

The shared semantic layer. One vocabulary in which a question (evidence), a
target (requirement) and an intervention (action) can all name the same thing.

```
                    CAPABILITY
                   /     |     \
           QUESTIONS   TARGET   INTERVENTIONS
               |         |          |
           evidence  requirement  action
```

Seeded by migration `f2a91c3d7b58`. **7 domains, 34 capabilities, 136 evidence
criteria, 354 intervention mappings.** Nothing in the application reads these
tables yet.

---

## Why a new vocabulary

Three existing vocabularies were inspected first. None of them is a capability
taxonomy, and the reasons are different in each case.

| Candidate | What it actually is | Verdict |
|---|---|---|
| `interventions.capability_domain` | 417 rows, ~390 near-unique free-text labels — "Opening Line Craft", "Sunk Cost Psychology". One label per intervention | **Mapping source only.** A naming convention, not a vocabulary |
| `readiness_pillars` (6) | Diagnostic **scoring axes**. Every description begins *"Measures the founder's ability to…"* | **Referenced, not adopted.** `capabilities.pillar_id` so reports can group under a heading founders already see. They rate the founder today; a capability is a thing the business can do |
| `interventions.section` (12) | The same subject-area vocabulary as `questions.category`, plus five `Scaling — *` entries | **Not adopted.** Subject areas, not capabilities: four are GTM-ish and one ("Idea & Validation") is really a stage |

## Industry neutrality

There is no *SaaS Sales Capability* and no *Agriculture Sales Capability* —
there is `GTM-SALES Repeatable Sales System`. Context (industry × business model
× stage × target scale) belongs on the **requirement**, which Step 6 adds.
Duplicating capabilities per industry would put contextualisation in the wrong
table and make every new vertical a taxonomy change — the thing Steps 2–4 were
spent removing from the engine. Pinned by
`test_the_taxonomy_is_industry_neutral`.

## Levels

One scale for every capability, defined in
`app/api/v1/diagnosis/capability_levels.py`. The axis is **founder dependence**.

| Level | Meaning |
|---|---|
| 0 `ABSENT` | the thing does not happen, or happens by accident |
| 1 `PERSONAL` | it works because the founder personally does it |
| 2 `DOCUMENTED` | it exists outside the founder's head |
| 3 `OWNED` | someone other than the founder owns and improves it |

`UNASSESSED` is **not** a level and is deliberately not an enum member — it is a
string, so `UNASSESSED < CapabilityLevel.DOCUMENTED` raises `TypeError`. A
capability nobody asked about has no level; zero is a positive claim that the
thing is absent. This is the capability-level form of Step 4's rule that UNKNOWN
must never mean NO, and it is what will stop the Gap Engine manufacturing gaps.

Nothing stores a level yet. Step 8 introduces `capability_evidence`.

---

## The taxonomy

| Domain | Capability | Description | Interventions |
|---|---|---|---:|
| GTM | `GTM-ICP` Customer & Segment Clarity | Knowing precisely who the business sells to, and why they buy. | 10 |
| GTM | `GTM-ACQ` Repeatable Acquisition | Whether new customers arrive through a channel that can be repeated on purpose. | 30 |
| GTM | `GTM-SALES` Repeatable Sales System | A defined, teachable sales process rather than a series of improvisations. | 23 |
| GTM | `GTM-PIPE` Pipeline Visibility & Forecasting | Knowing what is in the pipeline and what is likely to close. | 14 |
| GTM | `GTM-OWN` Sales Ownership Beyond the Founder | Whether anyone other than the founder can win business. | 2 |
| GTM | `GTM-RETAIN` Retention & Expansion | Whether existing customers stay, and grow. | 14 |
| FOUNDER | `FND-TIME` Founder Time Allocation | Whether the founder's time goes to what only the founder can do. | 7 |
| FOUNDER | `FND-DELEG` Delegation & Decision Ownership | Whether decisions have owners other than the founder. | 15 |
| FOUNDER | `FND-INDEP` Operational Independence from the Founder | Whether the business keeps running when the founder steps away. | 3 |
| FOUNDER | `FND-FOCUS` Strategic Focus | Whether the founder holds a direction rather than reacting to whatever is loudest. | 10 |
| FOUNDER | `FND-LEAD` Leadership Capacity | Whether the founder can lead people, not just do the work. | 6 |
| ORG | `ORG-ROLES` Role Clarity & Ownership | Whether responsibilities are defined and owned. | 7 |
| ORG | `ORG-HIRE` Hiring Capability | Whether the business can define, attract and select the people it needs. | 8 |
| ORG | `ORG-PERF` Performance & Accountability | Whether performance is visible, discussed and acted on. | 13 |
| ORG | `ORG-CADENCE` Management Cadence & Communication | Whether the organisation has a rhythm for deciding and informing. | 9 |
| ORG | `ORG-CULTURE` Culture & Retention | Whether people want to stay and know what is expected of them. | 7 |
| OPS | `OPS-PROCESS` Repeatable Processes | Whether core work happens the same way each time. | 7 |
| OPS | `OPS-SOP` Documentation & SOPs | Whether how-to knowledge lives outside individual heads. | 13 |
| OPS | `OPS-QUALITY` Quality Control | Whether defects are caught before the customer finds them. | 4 |
| OPS | `OPS-MONITOR` Operational Monitoring | Whether the founder can see operational health without asking someone. | 9 |
| OPS | `OPS-TOOLING` Systems & Tooling | Whether the tools in use match the scale of the work. | 6 |
| FIN | `FIN-VIS` Financial Visibility | Whether the founder can see the numbers, accurately and on time. | 14 |
| FIN | `FIN-UNIT` Unit Economics | Whether the founder knows what each unit of business earns and costs. | 20 |
| FIN | `FIN-CASH` Cash & Runway Planning | Whether cash is forecast rather than discovered. | 12 |
| FIN | `FIN-PLAN` Financial Planning & Budgeting | Whether spending follows a plan that is reviewed. | 10 |
| FIN | `FIN-INVEST` Investor Readiness | Whether the business can withstand external financial scrutiny. | 17 |
| PROD | `PRD-DISCOVER` Customer Discovery & Validation | Whether what gets built is grounded in evidence from real customers. | 14 |
| PROD | `PRD-DELIVERY` Delivery Predictability | Whether what is promised ships when it was said to. | 3 |
| PROD | `PRD-FEEDBACK` Feedback Loops | Whether what customers experience gets back to the people building. | 5 |
| PROD | `PRD-ROADMAP` Roadmap & Prioritisation Discipline | Whether what to build next is decided rather than reacted to. | 6 |
| STRAT | `STR-POSITION` Positioning & Differentiation | Whether the business can say why it is the right choice. | 10 |
| STRAT | `STR-MODEL` Business Model Design | Whether the way the business makes money is deliberate and sound. | 5 |
| STRAT | `STR-COMPETE` Competitive Awareness | Whether decisions account for what the market is doing. | 7 |
| STRAT | `STR-PLAN` Planning & Goal Setting | Whether there are goals, and whether progress against them is known. | 14 |

---

## Intervention mapping

| | Count |
|---|---:|
| Interventions | 417 |
| **Mapped** | **328** (354 pairs — 26 build more than one capability) |
| Founder-psychology, out of scope | 75 |
| Ambiguous, not forced | 14 |

### Founder psychology is deliberately unmapped

75 interventions are about the founder's **inner state** — "Burnout Recovery",
"Imposter Syndrome", "Sunk Cost Psychology", "Identity Separation". They are not
mapped, and that is not an omission:

- a capability is something the **business** can do;
- the *Founder Readiness* pillar and the `psychological_state` engine already
  cover inner state;
- mapping them would make this a founder-personality taxonomy, which §5 of the
  step brief explicitly forbids.

The `FOUNDER` domain here is founder **scalability** — delegation, time
allocation, operational independence — which is a property of the business, not
of the person.

### Ambiguous — reported rather than forced

Each of these could defensibly map to two or more capabilities. Forcing them
would put noise into the one table three later steps depend on.

| Intervention | Section | Label |
|---|---|---|
| `INT-051` | Scaling — Operational Scaling | Onboarding |
| `INT-053` | Scaling — Operational Scaling | Management Design |
| `INT-065` | Scaling — Revenue Management | Revenue Compliance |
| `INT-071` | Scaling — People Management | Compensation Strategy |
| `INT-148` | Opportunity Evaluation | Decision Feedback Loop |
| `INT-215` | Marketing Execution | Pre-Launch Market Timing Check |
| `INT-297` | Go-To-Market | GTM System Building |
| `INT-298` | Go-To-Market | Revenue-Linked Metrics |
| `INT-299` | Go-To-Market | Tactic Discipline |
| `INT-331` | Sales & Revenue | Expectation & Fit Alignment |
| `INT-346` | Team & Leadership | Governance Infrastructure |
| `INT-347` | Team & Leadership | Governance Priority Shift |
| `INT-443` | Founder Psychology | Structured Pivot Evaluation |
| `INT-445` | Founder Psychology | Decision-Making Tools |

---

## Taxonomy gaps discovered

**`GTM-OWN` Sales Ownership Beyond the Founder maps to only 2 interventions**
(`INT-056 Revenue Operations`, `INT-064 Sales Compensation`). This is the
thinnest capability in the taxonomy and it is also the one a ₹1 Cr → ₹10 Cr
founder most needs: the library has a great deal about how the founder should
sell better, and almost nothing about handing sales to someone else. A
content gap, not a taxonomy error — worth a brief to Arya before Step 9.

`FND-INDEP` (3) and `OPS-QUALITY` (4) are also thin, for the same reason: the
library is stronger on founder skill than on founder replacement.

---

## Remaining curation

| Task | Size | Status |
|---|---|---|
| `question_capabilities` | ~3,460 questions | **0 mapped.** Table created, deliberately empty |
| Ambiguous interventions | 14 | Need an editorial decision |
| `GTM-OWN` content | — | Library gap, not a mapping gap |

A fabricated question mapping would produce confident evidence about
capabilities nobody checked, so the table ships empty. An unmapped question
simply yields no capability evidence — the same fail-open every other optional
map in this codebase uses.
