/**
 * data/glossary.js — the founder glossary under "Things to learn".
 *
 * SOURCE: GoXL_Founder_Glossary_v2.docx (September 2026) — "The Founder
 * Glossary: every term a founder needs across all 12 areas of building a
 * business". 243 terms.
 *
 * GENERATED FROM THE DOCUMENT, NOT RETYPED. 243 entries across four fields is
 * close to a thousand chances to introduce a silent transcription error, and a
 * glossary whose definitions are subtly wrong is worse than no glossary. The
 * generator is scratchpad/gen_glossary.py; re-run it when the document changes
 * rather than hand-editing this file.
 *
 * THREE FIELDS PER TERM, from the document's own columns:
 *
 *   full     the expansion, when the term is an acronym. The document uses an
 *            em dash for terms that are not; those carry no `full` at all
 *            rather than a dash a reader has to decode.
 *   usedFor  the situation where the term earns its keep.
 *   means    the plain-language explanation. The document calls this the
 *            column that matters most, so it is what a card leads with.
 *
 * THIS REPLACED an earlier 182-term version built from
 * ally-founder-glossary.md. That one carried a `mistake` field — the failure
 * mode attached to each term. This document does not have that column, so the
 * field is gone rather than half-populated.
 */

export const GLOSSARY = [
  {
    "slug": "customer",
    "title": "Customers, market and positioning",
    "blurb": "Who you serve, how big that is, and why they should pick you. Most founder confusion downstream starts with vagueness here.",
    "terms": [
      {
        "term": "ICP",
        "means": "The exact type of customer you are built to win — not everyone who could buy, but the narrow slice where you win fastest, cheapest and most profitably. A sharp ICP is a filter you say NO with.",
        "full": "Ideal Customer Profile",
        "usedFor": "Filtering leads, targeting ad spend, writing copy, qualifying deals, deciding what to build next"
      },
      {
        "term": "Buyer Persona",
        "means": "A fictional but evidence-based sketch of one real customer type. Powerful when built from actual interviews; useless when invented in a meeting room.",
        "usedFor": "Aligning marketing, sales and product around one specific human"
      },
      {
        "term": "TAM",
        "means": "Every rupee that could theoretically be spent on your category. Largely a vanity number — nobody has ever captured their TAM.",
        "full": "Total Addressable Market",
        "usedFor": "Sizing the opportunity in a pitch deck; sanity-checking ambition"
      },
      {
        "term": "SAM",
        "means": "The slice of TAM you can actually reach given your model, geography, language and channel.",
        "full": "Serviceable Addressable Market",
        "usedFor": "Realistic market sizing for strategy and investor conversations"
      },
      {
        "term": "SOM",
        "means": "What you can genuinely capture given your team, capital and competition. The only market number worth planning against.",
        "full": "Serviceable Obtainable Market",
        "usedFor": "Setting believable 1–3 year revenue targets"
      },
      {
        "term": "PMF",
        "means": "The point where customers pull the product out of your hands instead of you pushing it at them. If you are asking whether you have it, you do not.",
        "full": "Product–Market Fit",
        "usedFor": "Deciding when to stop iterating and start pouring fuel on growth"
      },
      {
        "term": "JTBD",
        "means": "People do not buy your product; they hire it to make progress in their life. Understand the job, not the demographic.",
        "full": "Jobs To Be Done",
        "usedFor": "Product prioritisation, messaging, understanding why people switch"
      },
      {
        "term": "USP",
        "means": "The one thing you do that competitors cannot easily copy or credibly claim.",
        "full": "Unique Selling Proposition",
        "usedFor": "Ads, packaging, pitch decks, the one-line answer to 'why you?'"
      },
      {
        "term": "UVP",
        "means": "A plain sentence stating who it is for, what it does, and why it is better. If it takes a paragraph, you do not have one yet.",
        "full": "Unique Value Proposition",
        "usedFor": "Homepage headline, sales deck opener, cold email first line"
      },
      {
        "term": "Positioning",
        "means": "The space you occupy in the customer's head relative to alternatives. You do not choose it — you earn it, and the market confirms it.",
        "usedFor": "Brand strategy, pricing power, defending against competitors"
      },
      {
        "term": "Segmentation",
        "means": "Cutting your market into groups that behave differently enough to deserve different treatment. If the segments behave the same, they are not segments.",
        "usedFor": "Serving different customer groups with different offers and pricing"
      },
      {
        "term": "Beachhead Market",
        "means": "The smallest market you can completely dominate before expanding. Win small deliberately so you can win big credibly.",
        "usedFor": "Choosing where to launch first when you cannot afford to be everywhere"
      },
      {
        "term": "VoC",
        "means": "Structured listening to what customers literally say, in their own words — not your polished summary of it.",
        "full": "Voice of Customer",
        "usedFor": "Roadmap decisions, copywriting, reducing churn"
      },
      {
        "term": "NPS",
        "means": "A 0–10 'would you recommend us' score, expressed as promoters minus detractors. Directionally useful, easily gamed. Watch the trend, not the number.",
        "full": "Net Promoter Score",
        "usedFor": "Tracking loyalty and word-of-mouth potential over time"
      },
      {
        "term": "CSAT",
        "means": "How happy someone was with a single touchpoint. Tactical feedback, not a strategic signal.",
        "full": "Customer Satisfaction Score",
        "usedFor": "Measuring one specific interaction — a delivery, a support ticket, an onboarding call"
      },
      {
        "term": "Moat",
        "means": "Whatever stops a better-funded competitor from copying you in six months — network effects, switching costs, brand, data, regulation, or unfair distribution.",
        "usedFor": "Defensibility conversations with investors, and with yourself"
      },
      {
        "term": "Category Creation",
        "means": "Inventing a new market instead of competing inside an existing one. Expensive, slow, and occasionally worth everything.",
        "usedFor": "Long-horizon brand strategy when you refuse to be compared"
      }
    ]
  },
  {
    "slug": "product",
    "title": "Product, build and delivery",
    "blurb": "How an idea becomes a shipped, working thing — and the vocabulary your engineers and designers already use.",
    "terms": [
      {
        "term": "MVP",
        "means": "The smallest thing you can build that still teaches you whether people want it. It is not a cheap version of the full product — it is an experiment with a user interface.",
        "full": "Minimum Viable Product",
        "usedFor": "Testing your riskiest assumption with the least possible spend"
      },
      {
        "term": "MLP",
        "means": "An MVP people actually enjoy using. In a saturated market, merely viable is invisible.",
        "full": "Minimum Lovable Product",
        "usedFor": "Launching into a crowded category where 'viable' is not enough"
      },
      {
        "term": "POC",
        "means": "A deliberately throwaway build. Never ship a POC — it was not made to survive contact with real users.",
        "full": "Proof of Concept",
        "usedFor": "Answering 'is this even technically possible?' before committing budget"
      },
      {
        "term": "Pilot",
        "means": "A time-boxed live deployment with one or a few real customers, usually paid. The bridge between demo and contract.",
        "usedFor": "De-risking a full rollout by running it small and real first"
      },
      {
        "term": "Roadmap",
        "means": "An ordered set of bets, not a delivery promise. Anything more than a quarter out is a hypothesis wearing a date.",
        "usedFor": "Aligning team, investors and clients on sequence and intent"
      },
      {
        "term": "Backlog",
        "means": "The list of requested-but-not-committed work. If it only ever grows, you are collecting, not prioritising.",
        "usedFor": "Holding everything you are consciously not doing right now"
      },
      {
        "term": "Sprint",
        "means": "A short fixed window — usually one or two weeks — in which scope is frozen and something ships.",
        "usedFor": "Giving the team a repeatable rhythm and a fixed finish line"
      },
      {
        "term": "User Story",
        "means": "'As a [user], I want [action], so that [outcome].' Forces you to state the why, not just the what.",
        "usedFor": "Writing requirements an engineer can actually build from"
      },
      {
        "term": "Acceptance Criteria",
        "means": "The specific, testable conditions that must be true for work to count as done. Write them before the work starts.",
        "usedFor": "Ending arguments about whether something is finished"
      },
      {
        "term": "Wireframe",
        "means": "A grey-box layout showing where things go, deliberately before how they look.",
        "usedFor": "Agreeing structure before spending money on visual design"
      },
      {
        "term": "Prototype",
        "means": "A clickable fake. Cheap to throw away, which is the entire point.",
        "usedFor": "Testing a flow with real users before a line of code is written"
      },
      {
        "term": "Design System",
        "means": "A reusable kit of components, colours, type and rules so nobody reinvents the button on every screen.",
        "usedFor": "Keeping a product visually coherent as more people touch it"
      },
      {
        "term": "Tech Debt",
        "means": "Shortcuts taken to move faster now, on which you pay interest later. Some debt is a smart trade; unmanaged debt compounds until velocity dies.",
        "full": "Technical Debt",
        "usedFor": "Deciding when to slow down and clean up versus keep shipping"
      },
      {
        "term": "Feature Creep",
        "means": "The product quietly growing features nobody validated, usually because saying no felt impolite.",
        "usedFor": "Diagnosing why launches keep slipping and the product feels bloated"
      },
      {
        "term": "Scope Creep",
        "means": "The agreed deliverable expanding while the price and deadline stay exactly where they were.",
        "usedFor": "Protecting margin and timelines on client or agency work"
      },
      {
        "term": "QA",
        "means": "Systematic testing before release. The cost of skipping it is always paid twice — once in support, once in reputation.",
        "full": "Quality Assurance",
        "usedFor": "Catching defects before your customer does"
      },
      {
        "term": "UAT",
        "means": "The actual end user confirms it solves their problem — a different question from whether the code runs.",
        "full": "User Acceptance Testing",
        "usedFor": "Final sign-off before go-live"
      },
      {
        "term": "Beta",
        "means": "A near-finished release given to a limited group who have been told things may break.",
        "usedFor": "Controlled exposure to real users before public launch"
      },
      {
        "term": "GA",
        "means": "Open to everyone, fully supported, with no 'we're still testing' excuse available.",
        "full": "General Availability",
        "usedFor": "Marking a product as fully, publicly launched"
      },
      {
        "term": "Iteration",
        "means": "One loop of build → measure → learn. Speed of iteration beats the quality of any single decision.",
        "usedFor": "Improving something in deliberate cycles rather than one big bet"
      },
      {
        "term": "API",
        "means": "A defined doorway through which one system requests something from another. It is how integrations, partnerships and platforms happen.",
        "full": "Application Programming Interface",
        "usedFor": "Letting your product talk to other software, and partners plug into you"
      }
    ]
  },
  {
    "slug": "growth",
    "title": "Growth, marketing and sales",
    "blurb": "How a stranger becomes a customer, what that costs, and where the leak is.",
    "terms": [
      {
        "term": "GTM",
        "means": "Your complete plan for reaching and converting customers. A product without a GTM is a hobby.",
        "full": "Go-To-Market",
        "usedFor": "Planning a launch: who, where, how, at what price, through which channel"
      },
      {
        "term": "Funnel",
        "means": "The narrowing journey from awareness to purchase. You do not fix a funnel by adding traffic to a leaking stage.",
        "usedFor": "Diagnosing where prospects drop off"
      },
      {
        "term": "TOFU / MOFU / BOFU",
        "means": "Awareness, consideration and decision stages. Sending a bottom-funnel sales pitch to a top-funnel stranger is why cold outreach fails.",
        "full": "Top / Middle / Bottom of Funnel",
        "usedFor": "Matching content and offers to buyer readiness"
      },
      {
        "term": "Lead Magnet",
        "means": "Something genuinely useful given free in exchange for an email or phone number. If nobody would pay for it, it will not convert.",
        "usedFor": "Trading value for contact details"
      },
      {
        "term": "MQL",
        "means": "A lead that has shown enough interest to be worth a sales conversation — but has not asked for one yet.",
        "full": "Marketing Qualified Lead",
        "usedFor": "Deciding which leads marketing hands to sales"
      },
      {
        "term": "SQL",
        "means": "A lead sales has vetted and accepted as a genuine opportunity with budget, need and timing.",
        "full": "Sales Qualified Lead",
        "usedFor": "Filling the sales pipeline with real opportunities"
      },
      {
        "term": "PQL",
        "means": "A user whose in-product behaviour shows they are ready to pay. The most reliable signal of the three.",
        "full": "Product Qualified Lead",
        "usedFor": "Upselling free or trial users in a self-serve product"
      },
      {
        "term": "CAC",
        "means": "Total sales and marketing spend divided by new customers won. If CAC exceeds what a customer is worth to you, growth is just a faster way to run out of cash.",
        "full": "Customer Acquisition Cost",
        "usedFor": "Judging whether your marketing spend is efficient"
      },
      {
        "term": "LTV",
        "means": "The total gross profit a customer generates across their whole relationship with you. Calculate it on margin, not revenue, or you will lie to yourself.",
        "full": "Lifetime Value",
        "usedFor": "Deciding how much you can afford to spend acquiring a customer"
      },
      {
        "term": "LTV : CAC",
        "means": "How many rupees of value each rupee of acquisition buys. Below 3 is a warning; above 5 often means you are underinvesting in growth.",
        "full": "Lifetime Value to Customer Acquisition Cost Ratio",
        "usedFor": "Testing whether the business model scales"
      },
      {
        "term": "Payback Period",
        "means": "How many months of margin it takes to recover the CAC on one customer. Short payback beats a high LTV:CAC when cash is tight.",
        "usedFor": "Understanding how fast cash comes back"
      },
      {
        "term": "AOV",
        "means": "Average spend per transaction. Bundling, upsells and minimum-cart thresholds move this fastest.",
        "full": "Average Order Value",
        "usedFor": "Increasing revenue without increasing acquisition spend"
      },
      {
        "term": "ARPU",
        "means": "Total revenue divided by active users in a period. Rising ARPU with flat churn is the healthiest growth signal there is.",
        "full": "Average Revenue Per User",
        "usedFor": "Comparing monetisation across cohorts, plans or geographies"
      },
      {
        "term": "Conversion Rate",
        "means": "The percentage moving from one stage to the next. Doubling a 1% conversion is usually cheaper than doubling traffic.",
        "usedFor": "Finding the highest-leverage fix in the funnel"
      },
      {
        "term": "CTR",
        "means": "Clicks divided by impressions. A creative and messaging signal, not a business outcome.",
        "full": "Click-Through Rate",
        "usedFor": "Judging whether an ad, subject line or headline earns attention"
      },
      {
        "term": "CPC",
        "means": "What you pay each time someone clicks. Rising CPC with flat conversion means your creative or targeting is fatiguing.",
        "full": "Cost Per Click",
        "usedFor": "Managing paid media budgets"
      },
      {
        "term": "CPM",
        "means": "What you pay to be seen a thousand times. The currency of awareness campaigns.",
        "full": "Cost Per Mille (per thousand impressions)",
        "usedFor": "Buying reach and brand awareness"
      },
      {
        "term": "CPL",
        "means": "Spend divided by leads generated. Cheap leads that never close are the most expensive leads you can buy.",
        "full": "Cost Per Lead",
        "usedFor": "Comparing channel efficiency at the top of the funnel"
      },
      {
        "term": "CPA",
        "means": "What you pay for one defined conversion action. Effectively CAC at the channel level.",
        "full": "Cost Per Acquisition / Action",
        "usedFor": "Performance-marketing budgeting"
      },
      {
        "term": "ROAS",
        "means": "Revenue generated per rupee of ad spend. Note it uses revenue, not profit — a 4x ROAS on a 20% margin product still loses money.",
        "full": "Return On Ad Spend",
        "usedFor": "Judging paid campaigns in isolation"
      },
      {
        "term": "Churn Rate",
        "means": "The percentage of customers or revenue lost in a period. High churn turns growth into a treadmill.",
        "usedFor": "Measuring how fast you lose what you won"
      },
      {
        "term": "Retention Rate",
        "means": "The percentage who stay. Retention is the truest proxy for value delivered — it is very hard to fake.",
        "usedFor": "Measuring whether the product actually delivers"
      },
      {
        "term": "Cohort Analysis",
        "means": "Grouping customers by when they joined and tracking each group separately. Reveals truths that blended averages hide.",
        "usedFor": "Seeing whether the business is genuinely improving over time"
      },
      {
        "term": "K-Factor",
        "means": "How many new users each existing user brings. Above 1 means self-sustaining growth; almost nothing is above 1.",
        "full": "Viral Coefficient",
        "usedFor": "Assessing organic, referral-led growth"
      },
      {
        "term": "Pipeline",
        "means": "The total value of live opportunities, weighted by stage. A thin pipeline today is a bad quarter three months out.",
        "usedFor": "Forecasting revenue and spotting a dry quarter early"
      },
      {
        "term": "Sales Cycle",
        "means": "Average time from first contact to signed deal. It is nearly always longer than founders assume.",
        "usedFor": "Cash-flow planning and sales capacity planning"
      },
      {
        "term": "Win Rate",
        "means": "Deals closed divided by deals pursued. A low win rate with high volume usually means an unclear ICP.",
        "usedFor": "Diagnosing sales effectiveness versus lead quality"
      },
      {
        "term": "Attribution",
        "means": "Assigning credit for a sale to the channels that touched it. Always somewhat wrong; still better than guessing.",
        "usedFor": "Deciding where to put the next marketing rupee"
      },
      {
        "term": "SEO",
        "means": "Making your content the best answer to what your buyer searches. Slow to start, compounding once it works.",
        "full": "Search Engine Optimisation",
        "usedFor": "Earning traffic you do not pay for, every month, forever"
      },
      {
        "term": "SEM",
        "means": "Paid placement on search results. Instant, measurable, and it stops the moment you stop paying.",
        "full": "Search Engine Marketing",
        "usedFor": "Buying immediate visibility on high-intent searches"
      },
      {
        "term": "Drip Campaign",
        "means": "A pre-written sequence sent on a schedule or triggered by behaviour. The cheapest sales rep you will ever hire.",
        "usedFor": "Nurturing leads who are not ready to buy yet"
      }
    ]
  },
  {
    "slug": "economics",
    "title": "Unit economics and financial basics",
    "blurb": "The numbers that decide whether scaling makes you rich or bankrupt. This section extends the original GoXL unit-economics guide.",
    "terms": [
      {
        "term": "Unit Economics",
        "means": "The profit or loss on a single unit or a single customer. If one unit loses money, a thousand units lose a thousand times more.",
        "usedFor": "Testing whether the business works before you scale it"
      },
      {
        "term": "Selling Price",
        "means": "What you charge per unit before discounts. Pricing is a strategy decision disguised as an arithmetic one.",
        "usedFor": "Setting positioning, margin and competitiveness"
      },
      {
        "term": "Effective Selling Price",
        "means": "What you actually realise after discounts and schemes. Discounts silently erase margin while the price list stays flattering.",
        "usedFor": "Tracking real revenue, not list-price fantasy"
      },
      {
        "term": "Variable Cost",
        "means": "Cost that moves with every unit sold — materials, packaging, freight, payment gateway fees. Small leaks here become large at volume.",
        "usedFor": "Calculating contribution margin"
      },
      {
        "term": "Fixed Cost",
        "means": "Monthly cost that exists whether you sell zero or ten thousand — rent, salaries, subscriptions. High fixed cost is high risk in a downturn.",
        "usedFor": "Calculating breakeven and assessing downside risk"
      },
      {
        "term": "COGS",
        "means": "The direct cost of producing what you sold. Excludes marketing, admin and rent.",
        "full": "Cost of Goods Sold",
        "usedFor": "Computing gross margin"
      },
      {
        "term": "Gross Margin",
        "means": "Revenue minus COGS, as a percentage. Services businesses run 30–50%; software runs 70–90%. It sets the ceiling on everything else.",
        "usedFor": "Judging the fundamental quality of a business model"
      },
      {
        "term": "Contribution Margin",
        "means": "Revenue minus all variable costs, per unit. What each sale contributes toward fixed costs and profit. If this is near zero, volume will not save you.",
        "usedFor": "Deciding whether selling more actually helps"
      },
      {
        "term": "Net Margin",
        "means": "What is left after every single cost, including tax and interest. The number that pays you.",
        "usedFor": "The final answer on profitability"
      },
      {
        "term": "Breakeven Point",
        "means": "Fixed costs divided by contribution margin per unit — the volume at which you stop losing money. Below it you are funding customers; above it you are building a business.",
        "usedFor": "Knowing your survival line"
      },
      {
        "term": "Burn Rate",
        "means": "Net cash consumed per month. Gross burn is total spend; net burn is spend minus revenue. Always know both.",
        "usedFor": "Managing cash discipline month to month"
      },
      {
        "term": "Runway",
        "means": "Cash in bank divided by net monthly burn — months until zero. Under six months, fundraising becomes an emergency rather than a negotiation.",
        "usedFor": "Knowing how long you have to make it work"
      },
      {
        "term": "OPEX",
        "means": "Day-to-day running costs — salaries, rent, software, marketing. Hits the P&L immediately.",
        "full": "Operating Expenses",
        "usedFor": "Managing the ongoing cost of running the business"
      },
      {
        "term": "CAPEX",
        "means": "Money spent on long-lived assets like machinery, fit-outs or vehicles. Sits on the balance sheet and depreciates over years.",
        "full": "Capital Expenditure",
        "usedFor": "Planning major asset purchases and cash outflow"
      },
      {
        "term": "EBITDA",
        "means": "Operating profit stripped of financing and accounting effects. A proxy for core performance — and a favourite hiding place for genuine costs.",
        "full": "Earnings Before Interest, Taxes, Depreciation and Amortisation",
        "usedFor": "Comparing operating performance across companies; valuation in traditional industries"
      },
      {
        "term": "P&L",
        "means": "Revenue minus expenses over a period. Shows profitability, and says nothing about whether the cash actually arrived.",
        "full": "Profit and Loss Statement",
        "usedFor": "Answering 'did we make money this period?'"
      },
      {
        "term": "Balance Sheet",
        "means": "A snapshot at a single date: assets, liabilities and equity. The health-of-the-business document.",
        "usedFor": "Answering 'what do we own and what do we owe?'"
      },
      {
        "term": "Cash Flow Statement",
        "means": "Actual cash in and out. Profitable companies die from cash-flow failure far more often than from unprofitability.",
        "usedFor": "Answering 'where did the money actually go?'"
      },
      {
        "term": "Working Capital",
        "means": "Current assets minus current liabilities. Inventory-heavy businesses can be profitable and still starved of working capital.",
        "usedFor": "Funding day-to-day operations without borrowing"
      },
      {
        "term": "Cash Conversion Cycle",
        "means": "Days from paying your supplier to collecting from your customer. The longer it is, the more cash growth consumes.",
        "usedFor": "Diagnosing why a growing business feels cash-poor"
      },
      {
        "term": "DSO",
        "means": "Average days customers take to pay you. Every extra day is an interest-free loan you gave without agreeing to.",
        "full": "Days Sales Outstanding",
        "usedFor": "Chasing receivables and forecasting collections"
      },
      {
        "term": "Accrual vs Cash Accounting",
        "means": "Accrual records when it is earned or incurred; cash records when money moves. Accrual shows the truth of performance; cash shows the truth of survival.",
        "usedFor": "Choosing how you recognise revenue and cost"
      },
      {
        "term": "Depreciation",
        "means": "A non-cash expense recognising that assets wear out. Reduces taxable profit without reducing cash.",
        "usedFor": "Spreading the cost of an asset across its useful life"
      },
      {
        "term": "ROI",
        "means": "Gain from an investment relative to its cost. Simple, universal, and easy to manipulate by choosing a flattering time window.",
        "full": "Return On Investment",
        "usedFor": "Comparing where to put the next rupee"
      }
    ]
  },
  {
    "slug": "revenue",
    "title": "Revenue models and recurring revenue",
    "blurb": "If you sell subscriptions, retainers or contracts, this is the scoreboard investors and operators actually use.",
    "terms": [
      {
        "term": "MRR",
        "means": "Normalised, repeatable monthly revenue. One-off project fees do not belong in it, however tempting.",
        "full": "Monthly Recurring Revenue",
        "usedFor": "Tracking predictable monthly income and growth rate"
      },
      {
        "term": "ARR",
        "means": "MRR multiplied by twelve. Meaningful only if the revenue genuinely recurs.",
        "full": "Annual Recurring Revenue",
        "usedFor": "Headline metric for subscription businesses and investors"
      },
      {
        "term": "ACV",
        "means": "The annualised value of one customer contract. Rising ACV usually means you are moving upmarket.",
        "full": "Annual Contract Value",
        "usedFor": "Comparing deal sizes and setting sales targets"
      },
      {
        "term": "TCV",
        "means": "The complete value of a contract across its whole term, including one-offs.",
        "full": "Total Contract Value",
        "usedFor": "Understanding the full commitment in multi-year deals"
      },
      {
        "term": "Deferred Revenue",
        "means": "Money received in advance for service not yet delivered. It is cash in your account and a liability on your balance sheet.",
        "usedFor": "Managing cash collected but not yet earned"
      },
      {
        "term": "Logo Churn",
        "means": "The percentage of customers who left, regardless of their size.",
        "usedFor": "Counting customers lost"
      },
      {
        "term": "Revenue Churn",
        "means": "The percentage of recurring revenue lost. Losing one large account can look fine on logo churn and be catastrophic here.",
        "usedFor": "Measuring the financial impact of losses"
      },
      {
        "term": "GRR",
        "means": "Revenue retained from existing customers, excluding upsells. Caps at 100% — it can only reveal leakage.",
        "full": "Gross Revenue Retention",
        "usedFor": "Measuring how well you hold what you have"
      },
      {
        "term": "NRR / NDR",
        "means": "Retained revenue including expansion. Above 100% means you grow from existing customers alone, even with zero new sales.",
        "full": "Net Revenue Retention / Net Dollar Retention",
        "usedFor": "The single strongest signal of product value"
      },
      {
        "term": "Expansion Revenue",
        "means": "Additional revenue from existing customers via upgrades, seats or add-ons. The cheapest revenue in the business.",
        "usedFor": "Growing accounts without new acquisition cost"
      },
      {
        "term": "Land and Expand",
        "means": "Start with a small deployment, prove value, then grow inside the account. Slower to start, far cheaper to scale.",
        "usedFor": "Entering large organisations through a small door"
      },
      {
        "term": "Freemium",
        "means": "A permanently free tier that converts a small percentage to paid. Only works with very low serving costs and a clear upgrade trigger.",
        "usedFor": "Acquiring users at near-zero marginal cost"
      },
      {
        "term": "Rule of 40",
        "means": "Growth rate plus profit margin should exceed 40. Below it, you are neither growing fast enough nor profitable enough to justify the trade.",
        "usedFor": "Balancing growth against profitability"
      },
      {
        "term": "Magic Number",
        "means": "New recurring revenue generated per rupee of sales and marketing spend. Above roughly 0.75 signals it is safe to spend more.",
        "usedFor": "Assessing sales and marketing efficiency"
      },
      {
        "term": "Quick Ratio (SaaS)",
        "means": "New plus expansion revenue divided by churned plus contracted revenue. Above 4 is healthy; near 1 means you are running to stand still.",
        "usedFor": "Checking whether growth is real or just replacing losses"
      },
      {
        "term": "Usage-Based Pricing",
        "means": "Customers pay for what they consume. Lowers the barrier to entry, makes revenue harder to forecast.",
        "usedFor": "Aligning price with value delivered"
      },
      {
        "term": "Tiered Pricing",
        "means": "Good/Better/Best packaging. The middle tier is usually designed to be chosen; the top tier exists to make it look reasonable.",
        "usedFor": "Serving different willingness-to-pay with one product"
      },
      {
        "term": "Seat-Based Pricing",
        "means": "Price per user. Predictable and easy to sell, but it quietly penalises the customer for rolling you out widely.",
        "usedFor": "Monetising team adoption inside an organisation"
      }
    ]
  },
  {
    "slug": "funding",
    "title": "Fundraising, valuation and cap table",
    "blurb": "The language of raising outside money. Read this before your first investor call, not during it.",
    "terms": [
      {
        "term": "Bootstrapping",
        "means": "Funding the business from revenue and personal savings. Slower, and you keep control and every rupee of upside.",
        "usedFor": "Growing without outside capital"
      },
      {
        "term": "Pre-Money Valuation",
        "means": "The agreed value of the company before new money arrives. This number, not the cheque size, determines your dilution.",
        "usedFor": "Negotiating what your company is worth before investment"
      },
      {
        "term": "Post-Money Valuation",
        "means": "Pre-money valuation plus the amount invested. Investor ownership equals investment divided by post-money.",
        "usedFor": "Calculating ownership after a round"
      },
      {
        "term": "Dilution",
        "means": "The reduction of your ownership percentage as new shares are issued. A smaller slice of a much larger pie is usually the right trade — but do the arithmetic first.",
        "usedFor": "Understanding what each round costs you in ownership"
      },
      {
        "term": "Cap Table",
        "means": "The record of every shareholder and their stake. A messy cap table in the early years kills good deals later.",
        "full": "Capitalisation Table",
        "usedFor": "Tracking who owns what, and modelling future rounds"
      },
      {
        "term": "SAFE",
        "means": "An instrument converting to equity at a future priced round. No interest, no maturity date, and it will dilute you more than you expect if you stack several.",
        "full": "Simple Agreement for Future Equity",
        "usedFor": "Raising early money fast without setting a valuation"
      },
      {
        "term": "Convertible Note",
        "means": "A loan that converts into shares at the next round, usually with a discount and a cap. Unlike a SAFE, it carries interest and a maturity date.",
        "usedFor": "Bridging to a priced round with debt that becomes equity"
      },
      {
        "term": "Valuation Cap",
        "means": "The maximum valuation at which a SAFE or note converts. Rewards early risk; can cause severe founder dilution if set too low.",
        "usedFor": "Protecting early investors from paying a high later price"
      },
      {
        "term": "Term Sheet",
        "means": "A mostly non-binding summary of the investment terms. The economics matter; the control and preference clauses matter more.",
        "usedFor": "Agreeing deal terms before legal drafting begins"
      },
      {
        "term": "Due Diligence",
        "means": "A deep review of your financials, legal, tech, customers and team. Clean books and organised documents shorten it by weeks.",
        "usedFor": "The investor's verification process before wiring funds"
      },
      {
        "term": "Data Room",
        "means": "A structured, permissioned folder of everything an investor will ask for. Build it before you need it.",
        "usedFor": "Running an efficient fundraise"
      },
      {
        "term": "Lead Investor",
        "means": "The investor who sets terms, writes the largest cheque and brings others along. Rounds without a lead tend not to close.",
        "usedFor": "Getting a round moving"
      },
      {
        "term": "Liquidation Preference",
        "means": "The investor's right to recover their money before common shareholders. A 1x non-participating preference is standard; anything more is a red flag.",
        "usedFor": "Determining who gets paid first in an exit"
      },
      {
        "term": "Participating Preferred",
        "means": "The investor takes their money back AND shares the remainder. Also called double-dipping; resist it.",
        "usedFor": "Understanding a harsher preference structure"
      },
      {
        "term": "Anti-Dilution",
        "means": "Adjusts an investor's share price downward in a down round. Full-ratchet is punishing; broad-based weighted average is fair.",
        "usedFor": "Protecting investors if you raise at a lower price later"
      },
      {
        "term": "Down Round",
        "means": "Signals trouble, triggers anti-dilution, and damages morale. Usually preferable to running out of cash.",
        "usedFor": "Raising at a lower valuation than last time"
      },
      {
        "term": "Bridge Round",
        "means": "Short-term capital to reach a milestone. If you cannot name the milestone it bridges to, it is not a bridge — it is a delay.",
        "usedFor": "Buying time between two priced rounds"
      },
      {
        "term": "Pro-Rata Rights",
        "means": "The right to invest again in future rounds to avoid dilution. Standard for meaningful investors.",
        "usedFor": "Letting existing investors maintain their percentage"
      },
      {
        "term": "ESOP",
        "means": "Shares reserved for employees. Note that investors usually require the pool be created pre-money — meaning you fund it out of your own dilution.",
        "full": "Employee Stock Option Pool",
        "usedFor": "Attracting and retaining talent you cannot outbid in cash"
      },
      {
        "term": "Vesting",
        "means": "Shares that become yours gradually, typically over four years. Founders should vest too — it protects the company from an early departure.",
        "usedFor": "Ensuring equity is earned over time, not gifted upfront"
      },
      {
        "term": "Cliff",
        "means": "A minimum period, usually one year, before any equity vests at all. Leave before it and you leave with nothing.",
        "usedFor": "Protecting the cap table from short tenures"
      },
      {
        "term": "Drag-Along / Tag-Along",
        "means": "Drag-along forces minorities to join a majority-approved sale. Tag-along lets minorities join a majority's sale on the same terms.",
        "usedFor": "Governing how shares behave in an exit"
      },
      {
        "term": "Venture Debt",
        "means": "A loan for venture-backed companies, usually alongside equity. Cheaper in dilution, expensive in covenants and repayment pressure.",
        "usedFor": "Extending runway without giving up equity"
      },
      {
        "term": "Revenue-Based Financing",
        "means": "Capital repaid as a fixed percentage of monthly revenue. Non-dilutive and increasingly common for e-commerce and subscription businesses.",
        "usedFor": "Funding growth from predictable revenue"
      },
      {
        "term": "Traction",
        "means": "Demonstrated, measurable customer demand — revenue, retention, usage growth. It is the only pitch-deck slide that cannot be argued with.",
        "usedFor": "The evidence that persuades investors"
      },
      {
        "term": "DPIIT Recognition",
        "means": "Government recognition granting tax exemptions, easier compliance and access to schemes. Free to apply and worth doing early.",
        "full": "Department for Promotion of Industry and Internal Trade",
        "usedFor": "Accessing Indian startup benefits"
      }
    ]
  },
  {
    "slug": "legal",
    "title": "Legal, compliance and company structure (India)",
    "blurb": "The paperwork layer. Getting this wrong is rarely fatal on day one and frequently fatal at diligence.",
    "terms": [
      {
        "term": "Pvt Ltd",
        "means": "A separate legal entity with limited liability, shareholders and directors. Higher compliance burden, but the only structure most investors will fund.",
        "full": "Private Limited Company",
        "usedFor": "The default structure for any business that intends to raise capital or scale"
      },
      {
        "term": "LLP",
        "means": "Partnership flexibility with limited liability. Cheaper to maintain than a Pvt Ltd, but you cannot issue equity shares to investors.",
        "full": "Limited Liability Partnership",
        "usedFor": "Professional services and partner-led firms not seeking equity investment"
      },
      {
        "term": "OPC",
        "means": "A Pvt Ltd with a single shareholder. A reasonable starting point; convert before raising.",
        "full": "One Person Company",
        "usedFor": "A solo founder wanting limited liability without a co-founder"
      },
      {
        "term": "MoA",
        "means": "The charter document stating your objects and scope. Draft the objects clause broadly, or you will amend it later.",
        "full": "Memorandum of Association",
        "usedFor": "Defining what the company is legally allowed to do"
      },
      {
        "term": "AoA",
        "means": "The internal rulebook — share transfers, board powers, meetings. Investors will amend it at your first priced round.",
        "full": "Articles of Association",
        "usedFor": "Governing how the company runs internally"
      },
      {
        "term": "CIN",
        "means": "The unique 21-character registration number issued by the Registrar of Companies.",
        "full": "Corporate Identity Number",
        "usedFor": "Identifying your company in all official filings"
      },
      {
        "term": "DIN",
        "means": "A unique number every director must hold. Required before appointment.",
        "full": "Director Identification Number",
        "usedFor": "Legally serving as a company director"
      },
      {
        "term": "DSC",
        "means": "The digital equivalent of your signature for MCA and tax filings.",
        "full": "Digital Signature Certificate",
        "usedFor": "Signing statutory filings electronically"
      },
      {
        "term": "ROC",
        "means": "The government office your company legally answers to. Missed ROC filings attract per-day penalties that compound quietly.",
        "full": "Registrar of Companies",
        "usedFor": "All company registrations, filings and annual returns"
      },
      {
        "term": "GST / GSTIN",
        "means": "India's indirect tax. Registration is mandatory above the turnover threshold, and effectively mandatory to sell B2B or on marketplaces.",
        "full": "Goods and Services Tax / GST Identification Number",
        "usedFor": "Charging, collecting and claiming input tax on sales"
      },
      {
        "term": "TDS",
        "means": "You deduct tax before paying and deposit it with the government. Non-compliance disallows the expense and attracts interest.",
        "full": "Tax Deducted at Source",
        "usedFor": "Withholding tax on payments you make to vendors and staff"
      },
      {
        "term": "PAN / TAN",
        "means": "PAN identifies the entity for income tax; TAN is required specifically to deduct and deposit TDS.",
        "full": "Permanent Account Number / Tax Deduction Account Number",
        "usedFor": "Direct tax identity and TDS compliance"
      },
      {
        "term": "Udyam / MSME",
        "means": "Free registration granting MSME benefits, including a statutory right to interest on delayed customer payments.",
        "full": "Udyam Registration (Micro, Small and Medium Enterprises)",
        "usedFor": "Accessing priority lending, subsidies and delayed-payment protection"
      },
      {
        "term": "IEC",
        "means": "A mandatory code for import or export. Without it, no shipment clears customs.",
        "full": "Importer Exporter Code",
        "usedFor": "Any cross-border movement of goods"
      },
      {
        "term": "FSSAI",
        "means": "The licensing authority for food businesses. Category and labelling rules are strict and enforced.",
        "full": "Food Safety and Standards Authority of India",
        "usedFor": "Anything ingested, and many things applied to the body"
      },
      {
        "term": "DPDP Act 2023",
        "means": "India's data privacy law. Requires consent, purpose limitation, breach notification and defined data-fiduciary duties.",
        "full": "Digital Personal Data Protection Act, 2023",
        "usedFor": "Handling any personal data of Indian users"
      },
      {
        "term": "NDA",
        "means": "A contract binding parties to secrecy. Standard with vendors and employees; most serious investors will decline to sign one.",
        "full": "Non-Disclosure Agreement",
        "usedFor": "Protecting confidential information in early conversations"
      },
      {
        "term": "MoU",
        "means": "A statement of mutual intent, usually non-binding. Useful for alignment, useless for enforcement.",
        "full": "Memorandum of Understanding",
        "usedFor": "Recording intent before a binding contract exists"
      },
      {
        "term": "LOI",
        "means": "A preliminary document outlining proposed terms. Typically non-binding except for confidentiality and exclusivity clauses.",
        "full": "Letter of Intent",
        "usedFor": "Signalling serious intent to transact"
      },
      {
        "term": "SLA",
        "means": "Committed standards — uptime, response time, resolution time — usually with penalties. Enterprise clients will insist on one.",
        "full": "Service Level Agreement",
        "usedFor": "Defining what 'good service' contractually means"
      },
      {
        "term": "SHA",
        "means": "Defines rights, exits, board composition and what happens in a dispute. The document that decides who controls the company.",
        "full": "Shareholders' Agreement",
        "usedFor": "Governing the relationship between owners"
      },
      {
        "term": "Founders' Agreement",
        "means": "A written agreement on equity split, roles, vesting and exit between co-founders. Sign it while everyone still likes each other.",
        "usedFor": "Preventing the most common cause of startup death"
      },
      {
        "term": "Trademark",
        "means": "A registered mark giving exclusive rights in a class of goods or services. ™ signals a claim; ® means it is registered and enforceable.",
        "usedFor": "Protecting your brand name, logo and tagline"
      },
      {
        "term": "Patent",
        "means": "A 20-year monopoly on an invention in exchange for public disclosure. Expensive, slow, and irrelevant to most service businesses.",
        "usedFor": "Protecting a genuinely novel invention"
      },
      {
        "term": "Copyright",
        "means": "Automatic on creation for original work. Registration is not required but makes enforcement far easier.",
        "usedFor": "Protecting written, visual and code assets"
      },
      {
        "term": "Indemnity Clause",
        "means": "A promise to cover the other party's losses in defined situations. Read every uncapped indemnity twice.",
        "usedFor": "Allocating who pays when something goes wrong"
      },
      {
        "term": "Force Majeure",
        "means": "A clause suspending obligations during events outside anyone's control. Post-2020, expect it to be negotiated seriously.",
        "usedFor": "Excusing performance in genuinely extraordinary events"
      }
    ]
  },
  {
    "slug": "operations",
    "title": "Operations, supply chain and fulfilment",
    "blurb": "How the promise gets delivered. Product businesses live or die here; service businesses underestimate it.",
    "terms": [
      {
        "term": "SOP",
        "means": "A documented step-by-step method for a recurring task. The difference between a business and a job you own.",
        "full": "Standard Operating Procedure",
        "usedFor": "Making quality repeatable without the founder in the room"
      },
      {
        "term": "SKU",
        "means": "A unique code for one specific sellable variant — size, colour, pack. SKU sprawl silently destroys margin and warehouse sanity.",
        "full": "Stock Keeping Unit",
        "usedFor": "Tracking inventory, pricing and sales by exact variant"
      },
      {
        "term": "BOM",
        "means": "The complete list of components and quantities needed to make one unit. Your true COGS starts here.",
        "full": "Bill of Materials",
        "usedFor": "Costing a product accurately before you price it"
      },
      {
        "term": "MOQ",
        "means": "The smallest quantity a supplier will produce. High MOQs lock up working capital in slow-moving stock.",
        "full": "Minimum Order Quantity",
        "usedFor": "Negotiating with suppliers and planning cash"
      },
      {
        "term": "Lead Time",
        "means": "Time from placing an order to receiving usable goods. Underestimating it causes stockouts; overestimating it causes dead capital.",
        "usedFor": "Planning when to reorder"
      },
      {
        "term": "Inventory Turnover",
        "means": "How many times you sell and replace inventory in a year. Low turnover means your cash is sitting on a shelf.",
        "usedFor": "Measuring how efficiently stock converts to cash"
      },
      {
        "term": "Safety Stock",
        "means": "Buffer inventory held against surprises. Insurance you pay for in working capital.",
        "usedFor": "Absorbing demand and supply variability"
      },
      {
        "term": "Stockout",
        "means": "Running out of a sellable item. Costs the sale, the customer, and often the marketplace ranking.",
        "usedFor": "Diagnosing lost revenue you never see in reports"
      },
      {
        "term": "Dead Stock",
        "means": "Inventory that will not sell at full price. Discount it and free the cash; holding it hoping is not a strategy.",
        "usedFor": "Cleaning the balance sheet"
      },
      {
        "term": "Landed Cost",
        "means": "Product cost plus freight, duties, insurance and handling. Founders who price off ex-factory cost usually price too low.",
        "usedFor": "Knowing what a unit truly costs you"
      },
      {
        "term": "JIT",
        "means": "Receiving goods only as needed. Excellent for cash, fragile against supply disruption.",
        "full": "Just-In-Time",
        "usedFor": "Minimising inventory holding cost"
      },
      {
        "term": "3PL",
        "means": "A partner who stores, packs and ships for you. Buys speed and reach; costs margin and direct control.",
        "full": "Third-Party Logistics",
        "usedFor": "Outsourcing warehousing and fulfilment"
      },
      {
        "term": "Reverse Logistics",
        "means": "The entire process of getting a returned item back, inspected and restocked or written off. Almost always more expensive than founders model.",
        "usedFor": "Handling returns without bleeding margin"
      },
      {
        "term": "TAT",
        "means": "Time from request to completion. Publish it only if you can consistently beat it.",
        "full": "Turnaround Time",
        "usedFor": "Setting and meeting customer expectations"
      },
      {
        "term": "OTIF",
        "means": "The percentage of orders delivered complete and on schedule. The metric large buyers actually score you on.",
        "full": "On Time In Full",
        "usedFor": "Measuring delivery reliability, especially for B2B clients"
      },
      {
        "term": "Capacity Utilisation",
        "means": "How much of your available production or service capacity is being used. Consistently above 85% means you are about to have a quality problem.",
        "usedFor": "Deciding when to invest in more capacity"
      },
      {
        "term": "Bottleneck",
        "means": "The slowest step in a process. Improving anything other than the bottleneck improves nothing overall.",
        "usedFor": "Finding the one constraint limiting the whole system"
      },
      {
        "term": "QC",
        "means": "Inspecting output against a defined standard. Distinct from QA — QC checks the product, QA fixes the process.",
        "full": "Quality Control",
        "usedFor": "Catching defects before dispatch"
      },
      {
        "term": "Batch / Lot Number",
        "means": "A code identifying a production run. Legally required for food, cosmetics and pharma; commercially essential for any recall.",
        "usedFor": "Traceability and recall management"
      }
    ]
  },
  {
    "slug": "people",
    "title": "People, team and performance",
    "blurb": "The system that lets the business run without you being the answer to every question.",
    "terms": [
      {
        "term": "JD",
        "means": "A written statement of the role, responsibilities and outcomes. Vague JDs produce vague performance.",
        "full": "Job Description",
        "usedFor": "Hiring the right person and holding them to a clear standard"
      },
      {
        "term": "KRA",
        "means": "The 3–5 areas where a person must deliver results. Broad, stable and role-defining.",
        "full": "Key Result Area",
        "usedFor": "Defining what a role is fundamentally accountable for"
      },
      {
        "term": "KPI",
        "means": "The specific measurable numbers under each KRA. If you cannot count it, it is not a KPI.",
        "full": "Key Performance Indicator",
        "usedFor": "Measuring whether a KRA is being met"
      },
      {
        "term": "OKR",
        "means": "One ambitious objective with 3–5 measurable key results. Designed for stretch and alignment, not for calculating bonuses.",
        "full": "Objectives and Key Results",
        "usedFor": "Focusing an entire company on a few quarterly outcomes"
      },
      {
        "term": "RACI",
        "means": "A matrix assigning roles per task. Exactly one person is Accountable — that is the entire value of the framework.",
        "full": "Responsible, Accountable, Consulted, Informed",
        "usedFor": "Ending 'I thought you were doing it'"
      },
      {
        "term": "Span of Control",
        "means": "How many direct reports one manager has. Beyond seven or eight, coaching quality collapses.",
        "usedFor": "Designing a manageable org structure"
      },
      {
        "term": "Attrition Rate",
        "means": "The percentage of employees leaving in a period. Sudden spikes are a management signal long before they are an HR one.",
        "usedFor": "Measuring whether people stay"
      },
      {
        "term": "Onboarding",
        "means": "The structured first 30–90 days. Weak onboarding is the single largest predictor of early attrition.",
        "usedFor": "Getting a new hire productive fast"
      },
      {
        "term": "PIP",
        "means": "A documented plan with specific targets and a deadline. Use it to genuinely help or to exit cleanly — never as a delay tactic.",
        "full": "Performance Improvement Plan",
        "usedFor": "Formally addressing sustained underperformance"
      },
      {
        "term": "1:1",
        "means": "A recurring private conversation between manager and report. The cheapest retention tool available and the first thing founders cancel.",
        "full": "One-on-One",
        "usedFor": "Maintaining trust, context and early warning signals"
      },
      {
        "term": "CTC",
        "means": "Total annual cost of employing someone, including benefits and employer contributions. Always higher than take-home, which causes endless offer-stage friction.",
        "full": "Cost To Company",
        "usedFor": "Budgeting and communicating compensation in India"
      },
      {
        "term": "Bus Factor",
        "means": "How many people would have to disappear before the business stops. A bus factor of one is the most common founder blind spot.",
        "usedFor": "Assessing key-person risk"
      },
      {
        "term": "Founder-Market Fit",
        "means": "The match between your experience, network and obsessions and the market you chose. Investors weigh it more heavily than founders expect.",
        "usedFor": "Judging whether you are the right person for this problem"
      },
      {
        "term": "A-Player",
        "means": "Someone who raises the average performance of the team they join. One A-player usually outperforms three adequate hires.",
        "usedFor": "Setting a hiring bar"
      },
      {
        "term": "Culture Add",
        "means": "Hiring people who bring something the culture lacks — as opposed to 'culture fit', which quietly selects for people like you.",
        "usedFor": "Hiring for strength rather than sameness"
      },
      {
        "term": "Delegation",
        "means": "Transferring ownership of an outcome, not just a task. Handing over tasks while keeping every decision is not delegation; it is supervision.",
        "usedFor": "Removing yourself as the bottleneck"
      }
    ]
  },
  {
    "slug": "strategy",
    "title": "Strategy and decision-making",
    "blurb": "The thinking tools. These decide which problems you take on — and which you refuse.",
    "terms": [
      {
        "term": "Vision",
        "means": "The future you are trying to create. Long-range, directional, and largely unmeasurable — that is fine.",
        "usedFor": "Giving the company a destination"
      },
      {
        "term": "Mission",
        "means": "The concrete work you undertake in service of the vision.",
        "usedFor": "Explaining what you do about it every day"
      },
      {
        "term": "Values",
        "means": "The behaviours you reward and refuse. Values are only real when they cost you something — a client, a hire, a shortcut.",
        "usedFor": "Deciding behaviour when no rule applies"
      },
      {
        "term": "North Star Metric",
        "means": "The single metric that best captures the value you deliver to customers. Choose one that gets better only when customers genuinely win.",
        "usedFor": "Aligning every team on one number"
      },
      {
        "term": "Flywheel",
        "means": "A loop where each turn makes the next turn easier. Slow to start, near-unstoppable once spinning.",
        "usedFor": "Designing compounding rather than linear growth"
      },
      {
        "term": "SWOT",
        "means": "A four-box audit of internal and external factors. Useful as a conversation starter, dangerous as a conclusion.",
        "full": "Strengths, Weaknesses, Opportunities, Threats",
        "usedFor": "Structuring a fast strategic review"
      },
      {
        "term": "Porter's Five Forces",
        "means": "Analysis of supplier power, buyer power, new entrants, substitutes and rivalry. Explains why some hard-working businesses never make money.",
        "usedFor": "Assessing whether an industry is worth entering"
      },
      {
        "term": "Blue Ocean",
        "means": "Creating uncontested market space rather than fighting for share in a bloody one.",
        "usedFor": "Competing where nobody else is"
      },
      {
        "term": "First Principles Thinking",
        "means": "Breaking a problem to its irreducible truths and reasoning up from there, instead of reasoning by analogy to what others do.",
        "usedFor": "Solving problems nobody has solved for you"
      },
      {
        "term": "Opportunity Cost",
        "means": "The value of the best option you gave up by choosing this one. For a founder, the scarcest resource is attention, not money.",
        "usedFor": "Evaluating what a yes actually costs"
      },
      {
        "term": "Sunk Cost Fallacy",
        "means": "Continuing because of what you have already spent. Money already gone is irrelevant to whether the next rupee is well spent.",
        "usedFor": "Killing projects that should have died months ago"
      },
      {
        "term": "Pivot",
        "means": "A structured change of product, market or model based on evidence. A pivot keeps one foot planted; abandoning everything is a restart.",
        "usedFor": "Changing direction while keeping what you learned"
      },
      {
        "term": "Type 1 / Type 2 Decision",
        "means": "Type 1 is irreversible and deserves deliberation; Type 2 is reversible and deserves speed. Most founders treat Type 2 decisions as Type 1 and stall.",
        "usedFor": "Matching decision speed to decision stakes"
      },
      {
        "term": "Second-Order Thinking",
        "means": "Asking 'and then what happens?' at least twice. Discounts fix this quarter and destroy next year's pricing power.",
        "usedFor": "Avoiding solutions that create bigger problems"
      },
      {
        "term": "Pre-Mortem",
        "means": "Imagining the project has already failed, then listing why. Gets honest objections out of people who would not otherwise raise them.",
        "usedFor": "Surfacing risk before you commit"
      },
      {
        "term": "Pareto Principle",
        "means": "Roughly 80% of results come from 20% of causes. Applies to customers, revenue, defects and, uncomfortably, to your team.",
        "full": "80/20 Rule",
        "usedFor": "Finding disproportionate leverage"
      },
      {
        "term": "Theory of Constraints",
        "means": "Any system is limited by one constraint at a time. Find it, fix it, then find the next one.",
        "usedFor": "Improving a system rather than a step"
      },
      {
        "term": "Optionality",
        "means": "Preserving future choices at low present cost. Valuable when the future is unclear, expensive when it becomes an excuse not to commit.",
        "usedFor": "Staying flexible in uncertainty"
      }
    ]
  },
  {
    "slug": "psychology",
    "title": "Founder psychology, clarity and capacity",
    "blurb": "The layer most glossaries ignore and most businesses are actually limited by. GoXL's core thesis: the founder is the system.",
    "terms": [
      {
        "term": "Founder Bottleneck",
        "means": "The point where everything waits on one person's attention or approval. Almost always the real constraint before capital or market is.",
        "usedFor": "Diagnosing why growth stalled despite demand"
      },
      {
        "term": "Clarity Debt",
        "means": "Accumulated unmade decisions and undefined priorities. Like technical debt, it compounds — and it is paid in wasted team effort.",
        "usedFor": "Explaining why a busy team produces little"
      },
      {
        "term": "Working ON vs IN the Business",
        "means": "Working IN is doing the work; working ON is building the system that does the work. Most founders are trapped in the first and call it commitment.",
        "usedFor": "Deciding how a founder should spend the week"
      },
      {
        "term": "Owner's Trap",
        "means": "A business that cannot operate or be sold without you. Revenue can look healthy while enterprise value stays near zero.",
        "usedFor": "Recognising when you have built a job, not an asset"
      },
      {
        "term": "Decision Fatigue",
        "means": "The degradation of decision quality across a day of continuous choosing. Why the 6pm decision is usually the worst one.",
        "usedFor": "Protecting the quality of important choices"
      },
      {
        "term": "Context Switching",
        "means": "The mental cost of jumping between unrelated tasks. Each switch carries a real reload penalty measured in minutes.",
        "usedFor": "Understanding why a full day produced nothing"
      },
      {
        "term": "Deep Work",
        "means": "Extended, undistracted focus on cognitively demanding work. Strategy, positioning and product thinking cannot be done in fifteen-minute gaps.",
        "usedFor": "Producing the output only you can produce"
      },
      {
        "term": "Bandwidth",
        "means": "Your genuine available capacity, not your available hours. Founders routinely commit to calendar space they have no mental capacity to use.",
        "usedFor": "Honest capacity planning"
      },
      {
        "term": "Shiny Object Syndrome",
        "means": "Chasing each new opportunity before finishing the last. Feels like ambition; functions as avoidance.",
        "usedFor": "Explaining why three initiatives are all 60% done"
      },
      {
        "term": "Analysis Paralysis",
        "means": "Over-researching to postpone commitment. Usually a confidence problem presenting itself as a data problem.",
        "usedFor": "Breaking a stalled decision"
      },
      {
        "term": "Founder Dependency",
        "means": "The degree to which revenue, relationships and knowledge live only with the founder. The number one discount applied by acquirers.",
        "usedFor": "Assessing business resilience and saleability"
      },
      {
        "term": "Sustainable Pace",
        "means": "An operating intensity you can maintain for years rather than months. Endurance, not effort, is the actual scarce resource.",
        "usedFor": "Building a company that outlasts your energy"
      },
      {
        "term": "Founder-Business Alignment",
        "means": "The match between how you want to spend your life and what your business demands of you. Misalignment shows up as revenue growth alongside declining motivation.",
        "usedFor": "Checking whether the business still fits the person"
      }
    ]
  },
  {
    "slug": "goxl",
    "title": "The GoXL vocabulary",
    "blurb": "Proprietary GoXL language. Use these terms consistently across the platform, decks, proposals and the Ally knowledge library.",
    "terms": [
      {
        "term": "Clarity Before Action",
        "means": "Diagnose before you prescribe. Action taken without clarity is not speed — it is expensive motion.",
        "usedFor": "The GoXL operating philosophy across every engagement"
      },
      {
        "term": "3D Method",
        "means": "Understand the real problem, define the specific outcome, then execute. Most consulting starts at Deliver, which is why most consulting fails.",
        "full": "Diagnose → Define → Deliver",
        "usedFor": "The standard GoXL engagement structure"
      },
      {
        "term": "Founder Clarity Canvas",
        "means": "The GoXL 15-box framework mapping a founder's clarity across the business. The diagnostic instrument behind the Ally engine.",
        "usedFor": "Structured founder diagnosis"
      },
      {
        "term": "Five Pillars",
        "means": "The five layers a business is assessed against. Weakness at a lower pillar cannot be fixed by effort at a higher one.",
        "full": "Founder, Clarity, Structure, Execution, Scale",
        "usedFor": "Organising diagnosis and intervention"
      },
      {
        "term": "The GoXL Chain",
        "means": "Growth flows in one direction. Trying to scale before systems exist is the most common and most expensive founder error.",
        "full": "Founder → Clarity → Systems → Execution → Scale",
        "usedFor": "Explaining the GoXL causal model"
      },
      {
        "term": "Founder DNA",
        "means": "The behavioural, decision-making and energy profile of the individual founder — cross-validated against self-report, not just taken from it.",
        "usedFor": "Profiling how a specific founder operates"
      },
      {
        "term": "Business DNA",
        "means": "The structural, operational and market character of the business, assessed as a counterpart to Founder DNA.",
        "usedFor": "Profiling the business alongside its founder"
      },
      {
        "term": "PID",
        "means": "The diagnostic layer that identifies the real underlying problem rather than the presenting symptom.",
        "full": "Problem Identification & Diagnosis",
        "usedFor": "The reasoning engine inside GoXL Ally"
      },
      {
        "term": "RCA",
        "means": "Structured investigation of why a problem exists, powered in GoXL by a curated root-cause database. Treating symptoms guarantees recurrence.",
        "full": "Root Cause Analysis",
        "usedFor": "Getting past symptoms to causes"
      },
      {
        "term": "Ally",
        "means": "The Founder's Compass — an AI that understands the founder, the business and the situation before advising. Always written in full, never abbreviated.",
        "usedFor": "The GoXL AI founder companion product"
      },
      {
        "term": "Founder Clinic",
        "means": "A structured diagnostic session format delivered to founder cohorts and institutional partners.",
        "usedFor": "GoXL's institutional and campus programme format"
      },
      {
        "term": "Growth Partner",
        "means": "Not a vendor, not a consultant — an accountable partner in the outcome. The framing used across all GoXL proposals.",
        "usedFor": "How GoXL positions itself with clients"
      },
      {
        "term": "Grow10XLife",
        "means": "The public rallying identity behind GoXL's mission to help a million entrepreneurs build meaningful businesses.",
        "usedFor": "The GoXL movement identity"
      }
    ]
  }
];

/** Every term, counted once — used for the heading and the search count. */
export const GLOSSARY_TERM_COUNT = GLOSSARY.reduce((n, s) => n + s.terms.length, 0);
