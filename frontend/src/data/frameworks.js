/**
 * data/frameworks.js — the static content behind the Frameworks page.
 *
 * This is reference material, not a claim about the signed-in founder --
 * same category as HelpSupport's FAQ list. What's real about this founder's
 * relationship to each one (whether they've opened it, when, and any note
 * they wrote) lives in services/frameworks.js instead, not here.
 */

export const FRAMEWORKS = [
  {
    id: 'first-principles',
    title: 'First principles',
    tagline: 'Strip a complex decision back to what you actually know is true.',
    useWhen: 'The obvious answer keeps failing',
    whatItIs: 'Instead of reasoning by analogy — "competitors do X, so we should too" — you break a problem down into the facts you\'re certain of, then rebuild an answer from those facts alone. Named for the physics habit of not trusting an assumption just because it\'s common.',
    whenToUse: [
      'The "obvious" answer keeps not working, and you suspect it was borrowed from someone else\'s situation, not derived from yours.',
      'You\'re about to copy a competitor\'s move without knowing why it worked for them.',
      'A decision feels stuck because everyone in the room is arguing from a different unstated assumption.',
    ],
    howToApply: [
      'Write down the conclusion or plan you currently hold, in one sentence.',
      'List every assumption it rests on. Be exhaustive — include the ones that feel too obvious to write down.',
      'For each assumption, ask: is this a fact I can verify, or something I inherited from convention, a competitor, or a past version of myself?',
      'Discard anything that isn\'t independently true. What survives is your real foundation.',
      'Rebuild a plan from only what survived — even if it looks different from where you started.',
    ],
    example: 'A founder assumed pricing had to match competitors "because that\'s what the market does." Broken down: the actual constraint was margin needed to hit a 12-month runway, not competitor pricing. Rebuilt from that fact, the real price was 40% higher — and converted better, because it matched what the product actually delivered.',
  },
  {
    id: '80-20',
    title: '80 / 20',
    tagline: 'Find the small set of inputs producing most of the result.',
    useWhen: 'Effort is spread and nothing moves',
    whatItIs: 'The Pareto principle: in most systems, a small share of inputs accounts for most of the output. Applied to a business, a small share of customers, features, or activities usually explains most of the revenue, cost, or pain.',
    whenToUse: [
      'Effort feels spread thin across many things and nothing is clearly moving.',
      'You need to cut scope but don\'t know what\'s safe to cut.',
      'You suspect a small number of customers, channels, or bugs are doing most of the damage (or the driving).',
    ],
    howToApply: [
      'Pick one metric that matters (revenue, churn, support load, time spent).',
      'List the contributing items — customers, features, channels — and their share of that metric.',
      'Sort by contribution and find where the top ~20% accounts for ~80% of the total.',
      'Double down on that top slice; deliberately deprioritize or cut the long tail rather than serving it evenly.',
    ],
    example: 'A founder ranked customers by revenue and found the top 10 accounts were 34% of total revenue — and none of them were the accounts getting the most support attention. Support time got reallocated toward account health for that top decile instead of being spread evenly.',
  },
  {
    id: 'eisenhower-matrix',
    title: 'Eisenhower matrix',
    tagline: 'Separate what is urgent from what actually matters.',
    useWhen: 'Your week is full but goals do not move',
    whatItIs: 'A 2×2 grid that sorts tasks by urgency and importance. Urgent-and-important gets done now; important-but-not-urgent gets scheduled deliberately (this is where real progress hides); urgent-but-not-important gets delegated; neither gets dropped.',
    whenToUse: [
      'Your calendar is full but your actual goals haven\'t moved in weeks.',
      'You keep reacting to whoever asked most recently instead of what matters most.',
      'You want an honest answer to "what should I stop doing."',
    ],
    howToApply: [
      'List everything currently on your plate.',
      'For each, ask two separate questions: is this urgent (time-sensitive)? Is this important (moves a real goal)?',
      'Place each item in one of four quadrants: Do now, Schedule, Delegate, Drop.',
      'Protect time for "Important, not urgent" specifically — it\'s the quadrant everything else crowds out by default.',
    ],
    example: 'Reviewing a week\'s task list, a founder found "urgent" was almost entirely other people\'s requests routed through them by default, not genuine emergencies. Two of those got delegated outright; the freed time went to a roadmap decision that had been postponed for a month.',
  },
  {
    id: 'decision-matrix',
    title: 'Decision matrix',
    tagline: 'Compare options against criteria you set in advance.',
    useWhen: 'Two options both look defensible',
    whatItIs: 'A scoring table: list your real options as rows, the criteria that actually matter as columns, weight each criterion, score every option against every criterion, and let the totals — not your gut in the moment — surface the strongest choice.',
    whenToUse: [
      'Two or more options each have a good argument, and the debate is going in circles.',
      'You suspect the loudest voice in the room, not the best option, is about to win.',
      'You want a decision you can explain and defend later, not just recall making.',
    ],
    howToApply: [
      'List the real options — not a strawman and a foregone conclusion, actual candidates.',
      'List the criteria that matter (cost, speed, risk, team fit, reversibility) and assign each a weight.',
      'Score every option against every criterion, independent of which one you\'re rooting for.',
      'Multiply score × weight, sum per option, and treat the total as a strong input — not an automatic override of judgment it clearly missed.',
    ],
    example: 'Choosing between two hires who both interviewed well, weighting criteria (domain experience, culture fit, cost, speed to start) surfaced that the "obviously stronger" candidate scored lower once speed-to-start was weighted for a role that was already three months overdue.',
  },
  {
    id: 'swot',
    title: 'SWOT',
    tagline: 'Get a fast, honest read of position before a bigger decision.',
    useWhen: 'Before planning or a new market',
    whatItIs: 'Four honest questions in one grid: Strengths and Weaknesses (internal, within your control), Opportunities and Threats (external, outside your control). The value is less the grid and more the discipline of answering all four instead of only the flattering ones.',
    whenToUse: [
      'Before writing a plan for a new market, product line, or major bet.',
      'When a decision is being made on momentum rather than a clear-eyed read of position.',
      'Onboarding a new leader or investor who needs the real picture, not the pitch-deck version.',
    ],
    howToApply: [
      'Strengths: what do you have that competitors don\'t, provably (not aspirationally)?',
      'Weaknesses: what would a skeptical outsider flag in ten minutes with your numbers?',
      'Opportunities: what\'s shifting in the market, regulation, or customer behavior that you could exploit?',
      'Threats: what shift, if it happened, would hurt you the most — and how exposed are you to it right now?',
      'The point isn\'t the list — it\'s letting Weaknesses and Threats get equal airtime with the other two.',
    ],
    example: 'Before entering a new city, a SWOT surfaced that the team\'s biggest "strength" (a founder-led sales motion) was actually a weakness at the scale the new market needed — it didn\'t survive the founder not being in the room for every deal.',
  },
  {
    id: 'business-model-canvas',
    title: 'Business model canvas',
    tagline: 'See the whole business on one page and trace dependencies.',
    useWhen: 'One change might break another',
    whatItIs: 'A nine-block map of how a business actually works: customer segments, value proposition, channels, customer relationships, revenue streams, key resources, key activities, key partners, and cost structure — all on one page, so a change in one block\'s implications on the others are visible at a glance.',
    whenToUse: [
      'A change to one part of the business (pricing, channel, positioning) might have knock-on effects you haven\'t traced.',
      'Explaining the business to a new hire, board member, or advisor who needs the whole shape, not just the pitch.',
      'You suspect the business model has drifted from what it was originally designed to be.',
    ],
    howToApply: [
      'Fill in all nine blocks as the business actually operates today — not the aspirational version.',
      'For any change you\'re considering, find which block it touches directly.',
      'Trace outward: which other blocks does that one connect to? A channel change usually touches cost structure and customer relationships too.',
      'Only commit to the change once you\'ve looked at every block it touches, not just the one it was originally framed as.',
    ],
    example: 'A planned move from a sales-assisted to self-serve channel looked purely like a cost-structure win. Mapped against the full canvas, it also gutted the customer-relationship block that fed the highest-value renewals — caught before the change shipped, not after.',
  },
  {
    id: 'okrs',
    title: 'OKRs',
    tagline: 'Turn a vague ambition into something measurable.',
    useWhen: 'At the start of a quarter',
    whatItIs: 'Objectives (qualitative, ambitious, a sentence a person could rally behind) paired with Key Results (quantitative, verifiable, 2–4 per objective) that define what "done" honestly looks like. The objective is the "why," the key results are the only allowed answer to "did it actually happen."',
    whenToUse: [
      'At the start of a quarter or major initiative, before work starts, not after.',
      'When goals exist but nobody could tell you, today, whether they\'re on track.',
      'When "we\'re making progress" has stopped meaning anything specific.',
    ],
    howToApply: [
      'Write the Objective as a sentence a person outside the room would understand and find worth doing.',
      'Write 2–4 Key Results that are numbers, not activities — "signed 20 customers," not "worked on sales."',
      'Keep the total objective count small. Three is usually already too many to hold real focus on.',
      'Review against the key results on a fixed cadence — weekly or biweekly — not just at the end of the quarter when it\'s too late to correct course.',
    ],
    example: 'An objective of "make onboarding self-serve" had drifted into a list of engineering tasks with no way to tell if it worked. Rewritten with key results ("cut time-to-first-value from 9 days to 2," "hit 60% self-serve activation without a sales call"), the team caught at week 3 that a step they\'d shipped hadn\'t moved either number, and cut it.',
  },
  {
    id: 'ikigai',
    title: 'Ikigai',
    tagline: 'Check that your work still sits where meaning and capability meet.',
    useWhen: 'Motivation drops without a clear cause',
    whatItIs: 'Four overlapping circles — what you love, what you\'re good at, what the world needs, what you can be paid for — with the sweet spot in the middle. Originally a personal framework, useful for a founder checking whether the current version of the business (or their role in it) still sits in that overlap.',
    whenToUse: [
      'Motivation has dropped and you can\'t point to a single clear cause.',
      'The business is succeeding by external measures but doesn\'t feel worth the cost anymore.',
      'Deciding what to personally keep doing as the company grows past needing you everywhere.',
    ],
    howToApply: [
      'What you love: what parts of the work would you keep doing even unpaid?',
      'What you\'re good at: where do you produce outsized results with below-average effort?',
      'What the world needs: which of those, honestly, is something a market or a person is asking for?',
      'What you can be paid for: which of those, honestly, converts into revenue or a role someone would fund?',
      'Where fewer than four circles overlap, that\'s the misalignment worth naming — not necessarily fixing overnight, but naming.',
    ],
    example: 'A founder good at and paid for running sales personally realized they no longer loved it and it wasn\'t what the business most needed from them at its current stage — the overlap had moved toward hiring and systems, not the seat they were still occupying.',
  },
  {
    id: 'lean-startup',
    title: 'Lean startup',
    tagline: 'Design the smallest test that could change your mind.',
    useWhen: 'Before betting budget on an assumption',
    whatItIs: 'Build–Measure–Learn: turn an assumption into the smallest possible experiment, ship it fast, measure the real result, and let that result — not conviction — decide whether to persevere or pivot. The discipline is in "smallest," not in the build.',
    whenToUse: [
      'Before committing real budget or months of work to an assumption nobody has tested.',
      'When a debate about what customers want could be settled by asking five of them instead of arguing further.',
      'Early in a new product line or feature, before the cost of being wrong gets expensive.',
    ],
    howToApply: [
      'State the assumption as a falsifiable bet: "If we do X, Y% of users will do Z" — not a vague hope.',
      'Design the smallest, cheapest version of a test that could prove that bet wrong. Resist building more than that.',
      'Ship it, and measure the specific number you committed to upfront — not whichever number looks best afterward.',
      'Decide, based on that number alone: persevere (double down), pivot (change the approach), or kill it.',
    ],
    example: 'Instead of building a full self-serve onboarding flow, a two-week test offered it to 10% of new signups with a single manually-assembled screen. The number that mattered (activation rate) moved enough to justify the real build — a decision made in two weeks instead of two months.',
  },
];

export function getFramework(id) {
  return FRAMEWORKS.find((f) => f.id === id) || null;
}
