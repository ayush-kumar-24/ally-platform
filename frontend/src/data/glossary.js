/**
 * data/glossary.js — the founder's glossary under "Things to learn".
 *
 * WHERE THIS CAME FROM. ally-founder-glossary.md (7 Sep 2026). Unlike the film
 * and book lists, this one was already written to be read by a founder, so very
 * little needed re-addressing: what came out were the seeding instructions, the
 * internal document numbers, and the handful of asides written to the GoXL team
 * rather than to the reader.
 *
 * `mistake` IS THE POINT, not a footnote. Any dictionary can define CAC. What
 * makes this worth having is the failure mode attached to each term, which is
 * why it renders as its own line rather than being folded into the meaning or
 * hidden behind a hover.
 *
 * TWO SECTIONS OF THE SOURCE ARE NOT HERE.
 *
 * Section 11 is GoXL's own vocabulary -- stages, archetypes, pillars, the
 * Evolution Ladder. Its notes are internal ("unresolved", "at least three other
 * taxonomies in circulation"), it points at documents by number, and the source
 * itself says to reconcile it against those documents before use. Publishing a
 * second, slightly different definition of our own terms is exactly the problem
 * that note is warning about, so it waits for a decision.
 *
 * Section 10 IS here, with its verification date shown on the section. Those
 * facts move -- GST slabs, MSME limits and the DPDP phasing have all moved
 * inside a year -- and a founder reading a stale rate in our product would be
 * relying on us. The date is displayed rather than filed.
 */

export const GLOSSARY = [
  {
    slug: 'customer',
    title: 'Customer and market',
    terms: [
      {
        term: 'ICP (Ideal Customer Profile)',
        means: 'A description of the type of organisation or person you serve best — size, sector, situation, budget, urgency.',
        mistake: 'Founders write an ICP that describes who could buy instead of who buys fastest and stays longest. A real ICP excludes people. If it excludes nobody, it is not one.',
      },
      {
        term: 'Buyer persona',
        means: 'The individual human inside the ICP who feels the pain and signs off.',
        mistake: 'Distinct from the ICP. The company is the ICP; the frustrated ops manager is the persona. Selling to the wrong person inside the right company is the most common early sales failure.',
      },
      {
        term: 'Beachhead market',
        means: 'The first narrow segment you intend to dominate before expanding.',
        mistake: '"We will start with everyone and narrow later" never happens. Narrow is easier at the start, not harder.',
      },
      {
        term: 'Wedge',
        means: 'The single sharp use case you enter a customer with, before broadening.',
        mistake: 'A wedge is deliberately smaller than your ambition. Founders lead with the whole vision and land nothing.',
      },
      {
        term: 'TAM / SAM / SOM',
        means: 'Total market, the slice you can serve, and the slice you can realistically win.',
        mistake: 'TAM is the most inflated number in any pitch deck, and investors discount it automatically. The useful number is SOM, and almost nobody calculates it honestly.',
      },
      {
        term: 'Bottom-up market sizing',
        means: 'Realistic number of customers × realistic price × realistic frequency.',
        mistake: 'Always more credible than a top-down "1% of a $10bn market". If you cannot build it bottom-up, you do not understand your market.',
      },
      {
        term: 'PMF (Product-Market Fit)',
        means: 'The point where demand pulls harder than you push.',
        mistake: 'Not a badge. It is reversible, it is specific to a segment, and you can have it with one customer type and not another. Revenue alone is not proof.',
      },
      {
        term: 'Founder-market fit',
        means: 'Whether this founder is the right person for this market — domain access, credibility, and stamina for its timescale.',
        mistake: 'A separate constraint from PMF. A good market you have no right to win is still a bad market for you.',
      },
      {
        term: 'Product-founder fit',
        means: 'Whether you actually want to spend a decade on this problem.',
        mistake: 'Sounds soft, kills companies. Founders quit good businesses they were bored by.',
      },
      {
        term: 'JTBD (Jobs To Be Done)',
        means: 'The progress a customer is trying to make, which they "hire" your product for.',
        mistake: 'Reframes who you compete with. A restaurant’s competitor may be a ready meal, not another restaurant.',
      },
      {
        term: 'Problem-solution fit',
        means: 'Evidence that the problem is real and that your solution addresses it. It comes before PMF.',
        mistake: 'Skipping it and jumping to measuring PMF is why founders measure the wrong thing for a year.',
      },
      {
        term: 'Positioning',
        means: "The place your product occupies in the buyer's head, relative to the alternatives.",
        mistake: 'Not a tagline. It is a comparison. If the buyer has no frame of reference, they cannot value you.',
      },
      {
        term: 'Category creation',
        means: 'Building a market that does not exist yet.',
        mistake: 'Extremely expensive and slow — adoption can run ten to twenty years. It is a decision about the shape of your funding, not a marketing decision.',
      },
      {
        term: 'Early adopter',
        means: 'Someone who buys on the promise and tolerates rough edges.',
        mistake: 'Their enthusiasm is not evidence the mainstream will buy. The gap between them and the mainstream is where most traction dies.',
      },
      {
        term: 'Design partner',
        means: 'An early customer who co-builds with you, usually at a reduced price or none.',
        mistake: 'Only valuable if they give time, not just permission. An unpaid partner who gives you hours is worth more than a paying one who ignores you.',
      },
      {
        term: 'Voice of customer',
        means: 'Structured collection of what customers actually say, in their own words.',
        mistake: 'Founders paraphrase customers into their own language and lose the exact phrasing that would have made the marketing work.',
      },
      {
        term: 'Segment',
        means: 'A group of customers who behave the same way for the same reason.',
        mistake: 'If two customers buy for different reasons they are different segments, even if they look identical on paper.',
      },
    ],
  },

  {
    slug: 'growth',
    title: 'Growth, marketing and funnel metrics',
    terms: [
      {
        term: 'CAC (Customer Acquisition Cost)',
        means: 'Total sales and marketing spend divided by new customers acquired, over the same period.',
        mistake: "Founders quote paid CAC and hide salaries. If a person's time went into acquiring the customer, their cost belongs in CAC.",
      },
      {
        term: 'Blended vs paid CAC',
        means: 'Blended includes organic and referral; paid counts only the customers you bought.',
        mistake: 'Blended CAC flatters you early, while word of mouth is doing the work. Track both or you will misread the moment growth stalls.',
      },
      {
        term: 'LTV / CLV (Lifetime Value)',
        means: 'Total gross profit a customer generates over the whole relationship.',
        mistake: 'Use gross profit, not revenue. LTV on revenue is a vanity number, and for a services business it can be wildly wrong.',
      },
      {
        term: 'LTV:CAC ratio',
        means: 'How much value you get per rupee of acquisition cost.',
        mistake: '3:1 is folklore. Treat it as a direction, not a gate — it is meaningless before you know your real churn.',
      },
      {
        term: 'CAC payback period',
        means: 'Months of gross profit needed to earn back the cost of acquiring a customer.',
        mistake: 'More useful than LTV:CAC when cash is tight, because it is about when the cash comes back rather than whether it eventually does.',
      },
      {
        term: 'Funnel',
        means: 'The stages a stranger passes through to become a customer.',
        mistake: 'Founders optimise the middle. The biggest leaks are usually at the top — wrong audience — or the bottom, where there is no clear ask.',
      },
      {
        term: 'Conversion rate',
        means: 'The percentage moving from one stage to the next.',
        mistake: 'Meaningless without the stage definition. "20% conversion" from what, to what?',
      },
      {
        term: 'MQL / SQL',
        means: 'Marketing-qualified lead and sales-qualified lead.',
        mistake: 'Useful only if marketing and sales agree on the definition. In most companies they do not, and the handoff is where deals die.',
      },
      {
        term: 'Lead',
        means: 'Anyone who has shown any interest at all.',
        mistake: 'This word does more damage than any other here, because it makes a downloaded PDF look like demand.',
      },
      {
        term: 'Churn',
        means: 'The rate at which customers leave.',
        mistake: 'Separate logo churn (customers lost) from revenue churn (money lost). Losing ten small customers and losing one huge one are not the same event.',
      },
      {
        term: 'Retention',
        means: 'The inverse of churn — who stays.',
        mistake: 'A retention curve that flattens means a real product. One that keeps falling to zero means a leaky bucket, and every rupee of growth spend is wasted.',
      },
      {
        term: 'Cohort analysis',
        means: 'Grouping customers by when they joined and tracking each group over time.',
        mistake: 'The only honest way to see whether the product is improving. Aggregate numbers hide a worsening product behind growing volume.',
      },
      {
        term: 'Activation',
        means: 'The first moment a user gets real value.',
        mistake: 'If you cannot name your activation event, you cannot fix onboarding.',
      },
      {
        term: 'North star metric',
        means: 'The single number that best captures the value you deliver.',
        mistake: 'Pick one that goes up only when customers genuinely benefit. Pick badly and the whole team optimises the wrong thing.',
      },
      {
        term: 'Vanity metric',
        means: 'A number that rises reliably and predicts nothing — page views, downloads, followers, signups.',
        mistake: 'Not useless, but never a decision input. If a metric cannot go down when things go badly, it is not measuring anything.',
      },
      {
        term: 'ROAS',
        means: 'Return on ad spend — revenue generated per rupee of advertising.',
        mistake: 'Revenue, not profit. A great ROAS on a low-margin product can still lose money.',
      },
      {
        term: 'CPL / CPA / CPC / CPM',
        means: 'Cost per lead, per acquisition, per click, and per thousand impressions.',
        mistake: 'Ad-platform vocabulary. Know them so an agency cannot baffle you with them.',
      },
      {
        term: 'Attribution',
        means: 'Deciding which channel gets credit for a sale.',
        mistake: 'Genuinely hard, and getting less reliable. Do not rebuild your strategy on an attribution model you cannot audit.',
      },
      {
        term: 'K-factor / virality',
        means: 'How many new users each existing user brings.',
        mistake: 'Real virality is rare. Most "viral" growth is paid growth with a referral coat of paint.',
      },
      {
        term: 'Organic vs paid',
        means: 'Traffic you earned versus traffic you bought.',
        mistake: 'Organic looks free and is not — it costs time and content. Count that cost.',
      },
      {
        term: 'Top of funnel / bottom of funnel',
        means: 'Awareness-stage activity versus purchase-stage activity.',
        mistake: 'Founders short of cash usually over-invest at the top, which is exactly where payback is slowest.',
      },
    ],
  },

  {
    slug: 'revenue',
    title: 'Revenue and recurring-business metrics',
    terms: [
      {
        term: 'MRR / ARR',
        means: 'Monthly and annual recurring revenue.',
        mistake: 'Recurring means contractually repeating. One-off projects and pilots are not ARR, however much founders want them to be.',
      },
      {
        term: 'ACV (Annual Contract Value)',
        means: 'The annualised value of one customer contract.',
        mistake: 'Distinguish it from TCV, the total value across a multi-year deal. Mixing the two inflates your numbers by years.',
      },
      {
        term: 'ARPU / ARPA',
        means: 'Average revenue per user, or per account.',
        mistake: 'A single average across wildly different customers hides everything that matters. Segment it.',
      },
      {
        term: 'NRR / NDR (Net Revenue Retention)',
        means: 'Revenue from existing customers this year against last, including expansion and churn.',
        mistake: 'Above 100% means you would grow with zero new customers. The widely quoted 120% benchmark is enterprise-derived; private SMB medians run around 101–102%.',
      },
      {
        term: 'GRR (Gross Revenue Retention)',
        means: 'The same, but excluding expansion — the honest churn number.',
        mistake: 'NRR can look healthy while GRR is bleeding, if a few accounts are expanding fast. Always look at both.',
      },
      {
        term: 'Expansion revenue',
        means: 'More money from customers you already have.',
        mistake: 'The cheapest revenue in any business, and the most neglected by early founders chasing new logos.',
      },
      {
        term: 'Gross margin',
        means: 'Revenue minus the direct cost of delivering it, as a percentage.',
        mistake: 'The single most diagnostic number in a young business. A low gross margin caps everything you can afford to do later.',
      },
      {
        term: 'Contribution margin',
        means: 'Gross margin minus the variable cost of serving that customer.',
        mistake: 'The number that tells you whether each additional customer helps or hurts.',
      },
      {
        term: 'COGS',
        means: 'Cost of goods sold — the direct costs of delivery, such as hosting, materials and delivery staff.',
        mistake: 'Founders routinely park salaries in the wrong bucket, which makes gross margin meaningless.',
      },
      {
        term: 'Rule of 40',
        means: 'Growth rate plus profit margin should exceed 40.',
        mistake: 'Its author scopes it to companies at scale, roughly $50m of revenue and up. Applied to a ₹5 crore business it penalises exactly the profitable, steady profile it was never meant to describe.',
      },
      {
        term: 'Burn multiple',
        means: 'Net burn divided by net new ARR — how much you spend to add a rupee of recurring revenue.',
        mistake: 'A capital-efficiency check. Lower is better, and there is no credible universal benchmark.',
      },
      {
        term: 'Quick ratio (SaaS)',
        means: 'New plus expansion revenue, divided by churned plus contracted revenue.',
        mistake: 'Measures whether growth is outrunning leakage. The benchmarks widely quoted for it have no traceable source.',
      },
      {
        term: 'Magic number',
        means: 'Net new ARR divided by the prior period’s sales and marketing spend.',
        mistake: 'A rough test of sales efficiency. Useful directionally, and treated as far more precise than it is.',
      },
      {
        term: 'GMV',
        means: 'Gross merchandise value — the total value transacted through a marketplace.',
        mistake: 'Not revenue. Your revenue is the take rate on it. Confusing the two is the classic marketplace overstatement.',
      },
      {
        term: 'Take rate',
        means: 'Your percentage cut of GMV.',
        mistake: 'The number that decides whether a marketplace is a business or a charity.',
      },
      {
        term: 'Revenue vs bookings vs collections',
        means: 'Revenue earned, contracts signed, and cash actually received.',
        mistake: 'Three different numbers, quoted interchangeably. Only collections pay salaries.',
      },
    ],
  },

  {
    slug: 'cash',
    title: 'Cash, accounting and unit economics',
    terms: [
      {
        term: 'Unit economics',
        means: 'Whether one unit — one customer, one order, one project — makes money after all its direct costs.',
        mistake: 'If the unit loses money, scale makes it worse rather than better. This is the most-skipped calculation in early business.',
      },
      {
        term: 'Burn rate',
        means: 'Cash consumed per month. Gross burn is total spend; net burn is spend minus income.',
        mistake: 'Founders quote gross burn to sound lean and net burn to sound safe. Know which one you are being told.',
      },
      {
        term: 'Runway',
        means: 'Months of survival at the current net burn.',
        mistake: 'Recalculate it monthly. Runway based on last quarter’s burn, during a hiring spree, is fiction.',
      },
      {
        term: 'Default alive / default dead',
        means: 'Whether you reach profitability on current cash and growth, without raising again.',
        mistake: 'The most useful single question a founder can ask themselves, and most cannot answer it.',
      },
      {
        term: 'Break-even',
        means: 'The point where revenue covers costs.',
        mistake: 'Separate operational break-even, month to month, from cumulative break-even, which means paying back everything invested so far.',
      },
      {
        term: 'Working capital',
        means: 'Cash tied up in day-to-day operations — stock, unpaid invoices, supplier credit.',
        mistake: 'Profitable businesses die here. Growth consumes working capital, which is why growing fast can bankrupt you.',
      },
      {
        term: 'Cash conversion cycle',
        means: 'The days between paying for something and getting paid for it.',
        mistake: 'The real clock in any inventory or services business. Shortening it is often worth more than a price rise.',
      },
      {
        term: 'DSO (Days Sales Outstanding)',
        means: 'The average number of days customers take to pay.',
        mistake: 'In Indian B2B and government work this is frequently 60 to 120 days. Plan for the reality, not the invoice terms.',
      },
      {
        term: 'Accounts receivable / payable',
        means: 'Money owed to you, and money you owe.',
        mistake: 'Receivables are not cash. Never treat an invoice as money in the bank.',
      },
      {
        term: 'EBITDA',
        means: 'Earnings before interest, tax, depreciation and amortisation.',
        mistake: 'A proxy for operating performance. It is not cash flow, and treating it as cash flow has killed real companies.',
      },
      {
        term: 'Cash flow vs profit',
        means: 'Profit is accounting; cash flow is what is actually in the account.',
        mistake: 'You can be profitable and insolvent in the same month. Most first-time founders learn this the hard way.',
      },
      {
        term: 'Accrual vs cash accounting',
        means: 'Recording when something is earned or owed, versus when the money actually moves.',
        mistake: 'It determines what your P&L means. Know which basis your books are on before you read them.',
      },
      {
        term: 'CapEx vs OpEx',
        means: 'One-off asset purchases versus ongoing running costs.',
        mistake: 'Affects tax, the timing of cash, and how the business looks to a lender.',
      },
      {
        term: 'Fixed vs variable cost',
        means: 'Costs that do not move with volume, and costs that do.',
        mistake: 'Determines your break-even, and how badly a downturn hurts.',
      },
      {
        term: 'Operating leverage',
        means: 'How much profit grows as revenue grows, given your fixed-cost base.',
        mistake: 'High operating leverage is wonderful going up and brutal going down.',
      },
      {
        term: 'Depreciation / amortisation',
        means: 'Spreading the cost of an asset across its useful life.',
        mistake: 'This is why your P&L and your bank balance disagree.',
      },
      {
        term: 'Bootstrapping',
        means: 'Funding growth from revenue and your own money rather than from investors.',
        mistake: 'A legitimate strategy, not a consolation prize. It changes which metrics matter — payback period over lifetime value.',
      },
    ],
  },

  {
    slug: 'funding',
    title: 'Fundraising and cap tables',
    terms: [
      {
        term: 'Pre-money / post-money valuation',
        means: 'The value of the company before and after the new money goes in. Post equals pre plus the investment.',
        mistake: 'Founders agree a number without specifying which one they mean, and lose several percent doing it.',
      },
      {
        term: 'Dilution',
        means: 'The reduction in your ownership percentage when new shares are issued.',
        mistake: 'A smaller slice of a bigger pie is fine. A smaller slice of the same pie is not. Track it round by round.',
      },
      {
        term: 'Cap table',
        means: 'The register of who owns what.',
        mistake: 'Keep it clean and current from day one. A messy cap table kills more deals at diligence than bad numbers do.',
      },
      {
        term: 'ESOP pool',
        means: 'Shares reserved for employees.',
        mistake: 'The trap: investors usually require the pool to be created pre-money, so existing shareholders — mostly you — absorb the dilution. Negotiate its size and its timing.',
      },
      {
        term: 'Vesting / cliff',
        means: 'Earning your shares over time. The cliff is the minimum period before any of them vest.',
        mistake: 'Founders should vest too. Co-founder splits without vesting are the single most common cause of catastrophic early disputes.',
      },
      {
        term: 'Term sheet',
        means: "The non-binding outline of an investment's key terms.",
        mistake: 'The economics get all the attention. The control terms decide your life. Read those harder.',
      },
      {
        term: 'Priced round',
        means: 'A funding round with an agreed valuation, where shares are issued now.',
        mistake: 'The alternative is deferring the valuation through a convertible instrument.',
      },
      {
        term: 'Convertible note',
        means: 'Debt that converts into equity at a later round.',
        mistake: 'In India these are FEMA-regulated, with specific conditions for foreign investors. Take advice before using one across a border.',
      },
      {
        term: 'SAFE / iSAFE',
        means: 'Simple agreement for future equity — investment now, shares later, with no interest and no maturity. The India-adapted version is usually called an iSAFE.',
        mistake: 'Popular for speed. Stacking SAFEs without modelling the eventual dilution is a very common and very expensive error.',
      },
      {
        term: 'CCPS / CCD',
        means: 'Compulsorily convertible preference shares and debentures — the standard Indian instruments for priced institutional rounds.',
        mistake: 'Indian investors often prefer these to plain equity because of the preference rights attached. Understand what those rights let them do.',
      },
      {
        term: 'Valuation cap / discount',
        means: 'Limits on the conversion price of a note or SAFE, protecting the early investor.',
        mistake: 'The cap frequently becomes the de facto valuation. Set it as if it were one.',
      },
      {
        term: 'Liquidation preference',
        means: 'Who gets paid first when the company is sold, and how much.',
        mistake: '1x non-participating is the founder-friendly standard. Participating preferences mean investors get their money back and a share of the rest — on a modest exit you can walk away with almost nothing.',
      },
      {
        term: 'Participating vs non-participating',
        means: 'Whether the investor double-dips at exit.',
        mistake: 'Worth more than a valuation difference of several crore, and most first-time founders never check it.',
      },
      {
        term: 'Anti-dilution',
        means: 'Protection for investors if you later raise at a lower price.',
        mistake: 'Full ratchet is punitive; broad-based weighted average is the normal standard. Know which one you signed.',
      },
      {
        term: 'Pro-rata rights',
        means: "An investor's right to maintain their percentage in future rounds.",
        mistake: 'Reasonable to grant. Just know that it takes room away from future investors.',
      },
      {
        term: 'Down round',
        means: 'Raising at a lower valuation than the last one.',
        mistake: 'Survivable, but it triggers anti-dilution and damages morale. Usually the consequence of raising too high, too early.',
      },
      {
        term: 'Bridge round',
        means: 'Interim funding between proper rounds.',
        mistake: 'Sometimes a bridge, sometimes a pier. Ask honestly what it bridges to.',
      },
      {
        term: 'Runway-to-milestone',
        means: 'Raising enough to reach a specific proof point rather than just to survive.',
        mistake: 'The right way to size a raise. "Eighteen months of runway" with no milestone attached is just delayed panic.',
      },
      {
        term: 'Lead investor',
        means: 'The investor who sets the terms and anchors the round.',
        mistake: 'Without a lead, a round rarely closes. Chasing ten small cheques with no lead wastes months.',
      },
      {
        term: 'Due diligence',
        means: "The investor's verification process — legal, financial, technical and customer references.",
        mistake: 'Clean books and contracts make it fast. Mess makes it fatal.',
      },
      {
        term: 'Data room',
        means: 'The organised folder of documents investors review.',
        mistake: 'Prepare it before you raise, not during.',
      },
      {
        term: 'Drag-along / tag-along',
        means: 'The majority can force the minority to sell; the minority can join a majority sale.',
        mistake: 'Standard terms, but read the thresholds.',
      },
      {
        term: 'Board seat / observer',
        means: 'A vote in governance, versus attendance without a vote.',
        mistake: 'The composition of your board matters more than any single term in the document.',
      },
      {
        term: 'Secondary',
        means: 'Selling existing shares rather than issuing new ones.',
        mistake: 'How founders take some money off the table. Often restricted until later rounds.',
      },
      {
        term: 'Angel / pre-seed / seed / Series A',
        means: 'Rough stage labels for rounds.',
        mistake: 'The labels have drifted enormously. What matters is the evidence expected at each stage, not the name.',
      },
      {
        term: 'Venture debt',
        means: 'Loans to venture-backed companies, usually alongside equity.',
        mistake: 'Non-dilutive, but it is debt. It has covenants, and it must be repaid whatever happens.',
      },
      {
        term: 'Revenue-based financing',
        means: 'Capital repaid as a percentage of monthly revenue.',
        mistake: 'Useful when revenue is predictable, expensive when growth stalls.',
      },
      {
        term: 'Grant / subsidy',
        means: 'Non-dilutive government or institutional money.',
        mistake: 'Slow and paperwork-heavy, and genuinely free. Badly under-used by Indian founders.',
      },
    ],
  },

  {
    slug: 'sales',
    title: 'Sales and go-to-market',
    terms: [
      {
        term: 'Pipeline',
        means: 'The set of live opportunities, by stage and value.',
        mistake: 'A pipeline with no stage definitions and no next-step dates is a wish list.',
      },
      {
        term: 'Sales cycle',
        means: 'Time from first contact to signed contract.',
        mistake: 'Enterprise cycles of six to twelve months are normal. Bootstrapped founders routinely underestimate this and run out of cash mid-cycle.',
      },
      {
        term: 'Discovery call',
        means: "The conversation where you learn the customer's situation before pitching.",
        mistake: 'If you talked more than they did, it was not discovery.',
      },
      {
        term: 'Qualification (BANT / MEDDIC)',
        means: 'Frameworks for testing whether a deal is real — budget, authority, need and timing; or metrics, economic buyer, decision criteria, decision process, pain and champion.',
        mistake: 'Founders skip qualification because every conversation feels precious, then spend six months on a deal that never had a budget.',
      },
      {
        term: 'Champion',
        means: 'The person inside the customer who wants this to happen and will fight for it.',
        mistake: 'No champion, no deal. A friendly contact is not a champion — a champion spends their own political capital.',
      },
      {
        term: 'Economic buyer',
        means: 'The person who can actually release the money.',
        mistake: 'Often not the person you have been talking to.',
      },
      {
        term: 'POC / pilot',
        means: 'A time-boxed trial before a full purchase.',
        mistake: 'A real pilot has a budget, a business owner involved, agreed success criteria, and a stated path to purchase if it passes. Without those four it is theatre, and it will eat your quarter.',
      },
      {
        term: 'Land and expand',
        means: 'Win small, then grow inside the account.',
        mistake: 'It works because the hard costs — procurement, security review, onboarding — are paid once regardless of deal size.',
      },
      {
        term: 'PLG vs SLG',
        means: 'Product-led growth, where users adopt and then buy, versus sales-led growth.',
        mistake: 'Not a preference. It is determined by your price point, your buyer, and how self-evident the value is.',
      },
      {
        term: 'Inbound / outbound',
        means: 'Customers find you, or you find them.',
        mistake: 'Inbound is slower to build and cheaper to run. Outbound is the reverse. Most early companies need both.',
      },
      {
        term: 'SDR / AE / CSM',
        means: 'Sales development rep who books meetings, account executive who closes, customer success manager who retains and grows.',
        mistake: 'Splitting these roles too early is a classic over-hire. The founder does all three until the motion is proven.',
      },
      {
        term: 'Win rate',
        means: 'Deals won divided by deals seriously pursued.',
        mistake: 'A low win rate with high activity usually means a targeting problem, not an effort problem.',
      },
      {
        term: 'Free trial vs freemium',
        means: 'Time-limited full access, versus a permanently free tier.',
        mistake: 'Very different economics. Freemium suits consumer and prosumer products; it typically fails where the buyer needs security, compliance and deployment control.',
      },
      {
        term: 'Discount / price integrity',
        means: 'Reducing price to close a deal.',
        mistake: 'Every discount teaches the customer what you are really worth, and the renewal starts from there.',
      },
      {
        term: 'RFP / tender',
        means: 'A formal buying process, common in government and large enterprise.',
        mistake: "If you did not help shape the requirements, you are usually column fodder for someone else's deal.",
      },
      {
        term: 'MSA / SOW / NDA / LOI',
        means: 'Master service agreement, statement of work, non-disclosure agreement, letter of intent.',
        mistake: 'An LOI is not revenue. An NDA is not commitment. Know which document actually binds.',
      },
      {
        term: 'Procurement / vendor onboarding',
        means: "The customer's purchasing and compliance process.",
        mistake: 'For a small vendor this is often the longest part of the sale. Budget months, not weeks.',
      },
      {
        term: 'Reference customer',
        means: 'A customer willing to vouch for you publicly.',
        mistake: 'The most valuable asset in enterprise sales, and the one founders forget to ask for while goodwill is high.',
      },
      {
        term: 'Channel partner / reseller',
        means: 'Someone who sells on your behalf.',
        mistake: 'Rarely works before you can already sell it yourself. Partners amplify a working motion; they do not create one.',
      },
    ],
  },

  {
    slug: 'product',
    title: 'Product and delivery',
    terms: [
      {
        term: 'MVP',
        means: 'The smallest thing that tests your riskiest assumption with real users.',
        mistake: 'Not "version one, but worse". If it does not test an assumption, it is just an unfinished product.',
      },
      {
        term: 'Riskiest assumption test',
        means: 'Deliberately testing the belief that would kill the business if it were wrong.',
        mistake: 'A better framing than MVP for most founders, because it forces you to name the risk out loud.',
      },
      {
        term: 'Iteration / build-measure-learn',
        means: 'Short cycles of building, observing and adjusting.',
        mistake: 'The loop only works if you decided in advance what result would change your mind.',
      },
      {
        term: 'Roadmap',
        means: 'The sequenced plan of what you will build.',
        mistake: 'A roadmap that never changes is not being informed by customers. One that changes weekly is not a plan.',
      },
      {
        term: 'Backlog',
        means: 'The queue of things not yet built.',
        mistake: 'It grows forever. The skill is deletion, not prioritisation.',
      },
      {
        term: 'Scope creep',
        means: 'Requirements quietly expanding during delivery.',
        mistake: 'The main destroyer of margin in services and project businesses.',
      },
      {
        term: 'Technical debt',
        means: 'Shortcuts taken now that cost more later.',
        mistake: 'Sometimes correct to take deliberately. Dangerous when it is accidental and untracked.',
      },
      {
        term: 'SLA / uptime',
        means: 'A contractually promised level of service.',
        mistake: 'Enterprise buyers ask early. Promising 99.9% without knowing what it costs you to deliver is a trap.',
      },
      {
        term: 'Feature vs product vs company',
        means: 'A capability, a coherent whole someone buys, and a repeatable business around it.',
        mistake: 'Many "startups" are features. Useful, and they cannot support a company on their own.',
      },
      {
        term: 'Customisation vs configuration',
        means: 'Building something bespoke, versus adjusting settings.',
        mistake: 'Customisation for one customer feels like a win and quietly destroys repeatability.',
      },
    ],
  },

  {
    slug: 'people',
    title: 'People, hiring and organisation',
    terms: [
      {
        term: 'Scorecard (hiring)',
        means: 'A written definition of the outcomes a role must deliver, agreed before interviewing.',
        mistake: 'Most Indian SME hiring runs on a job description of duties, which predicts nothing. Outcomes predict.',
      },
      {
        term: 'Structured interview',
        means: 'The same questions, in the same order, scored the same way, for every candidate.',
        mistake: 'Dramatically more predictive than a free-flowing chat, and almost nobody does it.',
      },
      {
        term: 'Reference check',
        means: 'Speaking to people who actually worked with the candidate.',
        mistake: 'The most under-used, highest-yield step in hiring. Ask about specific behaviour, not general impressions.',
      },
      {
        term: 'Ramp time',
        means: 'How long a new hire takes to become productive.',
        mistake: 'For senior roles, plan nine to twelve months. The skill is spotting someone not ramping inside that window.',
      },
      {
        term: 'Span of control',
        means: 'How many people report to one manager.',
        mistake: 'Past about seven, the founder stops being able to actually manage. That is a structural signal, not a personal failing.',
      },
      {
        term: 'Founder-led everything',
        means: 'The stage where the founder personally does sales, hiring, support and product.',
        mistake: 'Correct early. It becomes the constraint on the whole business at a predictable point, usually between fifteen and thirty people.',
      },
      {
        term: 'Delegation vs abdication',
        means: 'Handing over a decision with context and accountability, versus simply dropping it.',
        mistake: 'Founders oscillate between the two. Real delegation includes extending the same error budget you claim for yourself.',
      },
      {
        term: 'Attrition',
        means: 'The rate at which employees leave.',
        mistake: 'Separate regretted from unregretted. Some attrition is the system working.',
      },
      {
        term: 'PIP (Performance Improvement Plan)',
        means: 'A formal, documented improvement process before an exit.',
        mistake: 'In India documentation matters legally. Handle exits properly or they become expensive.',
      },
      {
        term: 'Contractor vs employee',
        means: 'Different legal, tax and statutory obligations.',
        mistake: 'Misclassifying someone to save cost creates real liability. Get it right at the start.',
      },
      {
        term: 'ESOP (employee)',
        means: 'Share options granted to staff.',
        mistake: 'Only motivating if the employee understands strike price, vesting, exercise cost and tax. An unexplained ESOP is worth nothing as retention.',
      },
      {
        term: 'Sweat equity',
        means: 'Shares issued for work rather than for cash.',
        mistake: 'Regulated in India with specific limits and process. Never do it on a handshake.',
      },
      {
        term: 'Founder agreement / co-founder split',
        means: 'The written terms of equity, roles, vesting and exit between founders.',
        mistake: 'The most important document you will avoid writing. Write it while everyone still likes each other.',
      },
      {
        term: 'POSH compliance',
        means: "Statutory obligation under India's workplace sexual harassment law.",
        mistake: 'Mandatory once you cross the employee threshold, including an Internal Committee. Frequently missed by small firms.',
      },
      {
        term: 'Culture',
        means: 'The behaviour that actually gets rewarded and tolerated.',
        mistake: 'Not the values on the wall. It is what happens when a top performer behaves badly.',
      },
    ],
  },

  {
    slug: 'strategy',
    title: 'Strategy and competition',
    terms: [
      {
        term: 'Moat',
        means: 'A structural reason a competitor cannot easily take your customers.',
        mistake: 'Being better is not a moat. Being hard to switch away from is.',
      },
      {
        term: 'Switching cost',
        means: 'What it costs a customer to leave — money, data, retraining, risk.',
        mistake: 'Often the only real moat available to a small business. Design for it deliberately.',
      },
      {
        term: 'Network effect',
        means: 'The product gets more valuable as more people use it.',
        mistake: 'Genuinely rare. Most claimed network effects are just scale.',
      },
      {
        term: 'Economies of scale',
        means: 'Unit costs fall as volume rises.',
        mistake: 'Real in manufacturing, weaker in services, and sometimes absent entirely.',
      },
      {
        term: 'Differentiation',
        means: 'A difference the customer can perceive and cares about.',
        mistake: 'If they cannot perceive it, it does not exist commercially, however real it is technically.',
      },
      {
        term: 'Commoditisation',
        means: 'When competing offers become interchangeable and price is the only lever left.',
        mistake: 'The default destination of every category. Price today assuming it arrives.',
      },
      {
        term: 'Parity tax',
        means: 'Having to rebuild the boring features an incumbent already has, before your differentiation counts at all.',
        mistake: 'Replacement sales carry this cost and greenfield sales do not. Budget for it.',
      },
      {
        term: 'First-mover advantage',
        means: 'Being first to a market.',
        mistake: 'Overrated and often reversed — fast followers learn from your expensive mistakes.',
      },
      {
        term: 'Incumbent',
        means: 'The established player.',
        mistake: 'Their weakness is rarely the product. It is usually the business model or cost structure they cannot abandon.',
      },
      {
        term: 'Counter-positioning',
        means: 'Adopting a model the incumbent cannot copy without damaging their existing business.',
        mistake: 'The most reliable way for a small company to beat a large one.',
      },
      {
        term: 'Vertical vs horizontal',
        means: 'Serving one industry deeply, versus one function across many industries.',
        mistake: 'For Indian SMEs vertical depth is often the advantage, because relationship density inside one sector compounds.',
      },
      {
        term: 'Opportunity cost',
        means: 'The value of the best thing you gave up in order to do this.',
        mistake: 'The invisible cost in every founder decision, and the one never entered in the books.',
      },
      {
        term: 'Two-way vs one-way door',
        means: 'Reversible versus irreversible decisions.',
        mistake: 'Speed is correct for reversible decisions and reckless for irreversible ones. Most founders apply one speed to both.',
      },
      {
        term: 'Sunk cost fallacy',
        means: 'Continuing because of what you have already spent.',
        mistake: 'The most expensive bias in entrepreneurship. Money and years already spent are not evidence about the future.',
      },
      {
        term: 'Survivorship bias',
        means: 'Learning only from the ones who made it.',
        mistake: 'Why most business books mislead. The same behaviour is present in the failures; nobody wrote those up.',
      },
      {
        term: "Goodhart's law",
        means: 'When a measure becomes a target, it stops being a good measure.',
        mistake: 'Set a team a number and they will hit it, sometimes at the expense of the thing you actually wanted.',
      },
      {
        term: 'Confirmation bias',
        means: 'Seeking evidence that supports what you already believe.',
        mistake: 'Structurally dangerous in customer conversations, where founders ask questions designed to be agreed with.',
      },
    ],
  },

  {
    slug: 'india',
    title: 'India: legal, tax and compliance',
    /* Displayed, not filed. Every fact in this section was verified on one day
       and several of them have already moved once inside a year. A founder
       reading a stale rate here would be relying on us for it. */
    note: 'Verified 29 August 2026. These rules move — GST slabs, MSME limits and the DPDP timeline have all changed inside a year. Confirm anything here before you act on it.',
    terms: [
      {
        term: 'Pvt Ltd / LLP / OPC / sole proprietorship',
        means: 'The main Indian entity types.',
        mistake: 'The choice affects tax, your ability to raise, compliance load and personal liability. Investors will only fund a Pvt Ltd in practice. The OPC mandatory-conversion thresholds were removed in 2021, and many sources still quote them.',
      },
      {
        term: 'CIN / DIN / PAN / TAN',
        means: 'Company identifier, director identifier, tax identifier, and tax-deduction account number.',
        mistake: 'Basic identifiers you will be asked for constantly.',
      },
      {
        term: 'MOA / AOA',
        means: "Memorandum and articles of association — the company's constitutional documents.",
        mistake: 'The AOA governs share transfers and decision rights. Investors will want it amended; read what changes.',
      },
      {
        term: 'ROC / MCA filings',
        means: 'Annual filings with the Registrar of Companies.',
        mistake: 'Non-negotiable and penalty-bearing. Late filing costs escalate fast.',
      },
      {
        term: 'DIR-3 KYC',
        means: 'The director KYC filing.',
        mistake: 'Changed to once every three years, due 30 June, effective 31 March 2026 — no longer annual by 30 September. The cycle anchors to the year the DIN was allotted.',
      },
      {
        term: 'DPIIT recognition / Startup India',
        means: 'Government recognition as a startup, which unlocks specific benefits.',
        mistake: 'The definition was rewritten in February 2026 — the turnover ceiling rose to ₹200 crore, and a deep-tech category was added at 20 years and ₹300 crore. Most published guides are stale on this.',
      },
      {
        term: 'Section 80-IAC',
        means: 'The income-tax holiday for DPIIT-recognised startups.',
        mistake: 'The Income-tax Act 2025 replaced the 1961 Act on 1 April 2026. Rates are unchanged but section numbers changed — 80-IAC is now section 140.',
      },
      {
        term: 'Angel tax',
        means: 'Tax on share premium above fair value from Indian investors.',
        mistake: 'Abolished from AY 2025-26, which is FY 2024-25. Widely misreported by a year, including in decks that are still circulating.',
      },
      {
        term: 'GST / GSTIN',
        means: 'Goods and services tax, and your registration number for it.',
        mistake: 'The rate structure is now 5, 18 and 40 plus nil, effective 22 September 2025. The 12% and 28% slabs were abolished.',
      },
      {
        term: 'ITC (Input Tax Credit)',
        means: 'Offsetting GST paid on purchases against GST collected.',
        mistake: 'Blocked credits and supplier non-compliance are the two things that quietly destroy the benefit.',
      },
      {
        term: 'LUT (Letter of Undertaking)',
        means: 'Lets an exporter supply zero-rated without paying IGST upfront.',
        mistake: 'Essential for service exporters. It is a cash-flow instrument, not a formality.',
      },
      {
        term: 'RCM (Reverse Charge Mechanism)',
        means: 'The buyer pays the GST instead of the seller.',
        mistake: 'Applies to many imported services. The intermediary deeming provision was omitted with effect from 30 March 2026, which changed the position for Indian intermediaries serving foreign clients.',
      },
      {
        term: 'TDS',
        means: 'Tax deducted at source.',
        mistake: 'Your customers will deduct it from your invoices. It is cash-flow relevant, and reconciling it is real work.',
      },
      {
        term: 'MSME / Udyam registration',
        means: 'Registration as a micro, small or medium enterprise.',
        mistake: 'Limits were revised on 1 April 2025: micro ₹2.5cr investment and ₹10cr turnover; small ₹25cr and ₹100cr; medium ₹125cr and ₹500cr. The 45-day payment rule gives real leverage over large customers — micro and small only, traders excluded.',
      },
      {
        term: 'DPDP Act / Rules',
        means: "India's data protection law.",
        mistake: 'Rules were notified in November 2025 and are phased — consent-manager registration around November 2026, main obligations around May 2027. The older IT Act section 43A and SPDI Rules remain in force until then, so there is no compliance holiday.',
      },
      {
        term: 'FSSAI licence',
        means: 'The food business licence.',
        mistake: 'Turnover bands rose on 1 April 2026 and renewal was abolished in favour of perpetual validity — but the annual fee survives, and non-payment means deemed suspension. E-commerce food sellers and brand-owner head offices need a Central Licence at any turnover, so most direct-to-consumer brands get no relief. The brand owner is a full food business operator and cannot push liability onto a contract manufacturer.',
      },
      {
        term: 'EPF / ESI',
        means: 'Statutory provident fund and employee insurance.',
        mistake: 'Wage ceilings of ₹15,000 and ₹21,000 were unchanged as of August 2026 despite heavy press — but they are now revisable by notification alone, so they could move quickly.',
      },
      {
        term: 'Labour Codes',
        means: 'The four consolidated labour laws.',
        mistake: 'In force from 21 November 2025, but the implementing rules are largely un-notified, so practice is still in transition.',
      },
      {
        term: 'FEMA / FDI / ODI',
        means: 'The rules governing foreign investment into and out of India.',
        mistake: 'Any foreign investor, foreign subsidiary or overseas holding structure triggers these. Take advice before, not after.',
      },
      {
        term: 'FIRC',
        means: 'Foreign inward remittance certificate.',
        mistake: 'Proof that you received foreign currency. Needed for export benefits and for diligence.',
      },
      {
        term: 'SISFS (Startup India Seed Fund Scheme)',
        means: 'Government seed funding routed through approved incubators.',
        mistake: 'Non-dilutive or low-dilution capital that Indian founders consistently under-apply for.',
      },
      {
        term: 'Incubator / accelerator',
        means: 'Long-term support and space, versus a fixed-term cohort programme usually taken for equity.',
        mistake: 'Different things, often conflated. Judge either on the network it actually opens, not the branding.',
      },
    ],
  },
];

/** Every term, flattened — used for the count and for search. */
export const GLOSSARY_TERM_COUNT = GLOSSARY.reduce((n, s) => n + s.terms.length, 0);
