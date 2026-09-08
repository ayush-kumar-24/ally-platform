/**
 * data/glossary.js — the founder's glossary under "Things to learn".
 *
 * WHERE THIS CAME FROM. ally-founder-glossary.md (7 Sep 2026).
 *
 * WRITTEN IN PLAIN ENGLISH, ON PURPOSE. The source is written in fluent,
 * idiomatic business English -- "column fodder", "a referral coat of paint",
 * "sometimes a bridge, sometimes a pier". Most of the founders reading this do
 * not have English as a first language, and a glossary that needs a glossary is
 * worthless. So every line here is rewritten short and plain: common words,
 * one idea per sentence, no idioms, spoken directly to the reader.
 *
 * The technical terms themselves stay exactly as they are -- those are the
 * point, and a founder needs to recognise them when an investor says them.
 * What changed is the explanation around them.
 *
 * `mistake` IS THE POINT, not a footnote. Any dictionary can define CAC. What
 * makes this worth having is the mistake attached to each term, which is why it
 * renders as its own line rather than being folded into the meaning.
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
    title: 'Customers and market',
    blurb: 'Who you sell to, and how to tell one group from another.',
    terms: [
      {
        term: 'ICP (Ideal Customer Profile)',
        means: 'A short description of the kind of customer you serve best — their size, industry, situation, budget, and how badly they need you.',
        mistake: 'Most founders describe everyone who could buy. Describe who buys fastest and stays longest instead. A good ICP leaves people out. If it leaves nobody out, it is not doing its job.',
      },
      {
        term: 'Buyer persona',
        means: 'The actual person inside that company who feels the problem and signs the cheque.',
        mistake: 'This is not the same as the ICP. The company is the ICP. The tired operations manager is the persona. Selling to the wrong person inside the right company is the most common early mistake.',
      },
      {
        term: 'Beachhead market',
        means: 'The first small group you plan to win completely, before going wider.',
        mistake: 'Starting wide and narrowing later almost never happens. Starting narrow is easier, not harder.',
      },
      {
        term: 'Wedge',
        means: 'The one sharp problem you solve first, to get in the door.',
        mistake: 'A wedge is meant to be smaller than your full plan. Founders pitch the whole vision and win nothing.',
      },
      {
        term: 'TAM / SAM / SOM',
        means: 'The whole market, the part you can serve, and the part you can actually win.',
        mistake: 'TAM is the most exaggerated number in any pitch, and investors ignore it. The number that matters is the part you can actually win, and few founders work it out honestly.',
      },
      {
        term: 'Bottom-up market sizing',
        means: 'How many customers you can realistically get, times a realistic price, times how often they buy.',
        mistake: 'Far more believable than saying "1% of a ten-billion-dollar market". If you cannot build the number this way, you do not know your market yet.',
      },
      {
        term: 'PMF (Product-Market Fit)',
        means: 'The point where customers pull the product out of your hands, instead of you pushing it at them.',
        mistake: 'It is not a badge you keep. You can lose it. You can have it with one type of customer and not another. Revenue on its own does not prove it.',
      },
      {
        term: 'Founder-market fit',
        means: 'Whether you are the right person for this market. Do you know it, do people there trust you, and can you stay in it long enough.',
        mistake: 'This is separate from product-market fit. A good market you have no right to win is still the wrong market for you.',
      },
      {
        term: 'Product-founder fit',
        means: 'Whether you actually want to spend the next ten years on this problem.',
        mistake: 'It sounds soft. It closes companies. Founders walk away from good businesses because they were bored.',
      },
      {
        term: 'JTBD (Jobs To Be Done)',
        means: 'The job a customer is trying to get done. They "hire" your product to do it.',
        mistake: 'It changes who you think you compete with. A restaurant may be competing with a ready-made meal, not with the restaurant next door.',
      },
      {
        term: 'Problem-solution fit',
        means: 'Proof that the problem is real and that your solution fixes it. This comes before product-market fit.',
        mistake: 'Skip it and you can spend a year measuring the wrong thing.',
      },
      {
        term: 'Positioning',
        means: "Where your product sits in the buyer's mind, compared with the other options.",
        mistake: 'It is not a tagline. It is a comparison. If the buyer has nothing to compare you with, they cannot judge what you are worth.',
      },
      {
        term: 'Category creation',
        means: 'Building a market that does not exist yet.',
        mistake: 'Very slow and very expensive. It can take ten to twenty years. That makes it a decision about funding, not about marketing.',
      },
      {
        term: 'Early adopter',
        means: 'Someone who buys on the promise, and puts up with a rough product.',
        mistake: 'Their excitement does not prove ordinary customers will buy. Most growth dies in the gap between the two.',
      },
      {
        term: 'Design partner',
        means: 'An early customer who helps you build, usually for a low price or for free.',
        mistake: 'Only worth it if they give you their time, not just their permission. A free partner who gives you hours is worth more than a paying one who ignores you.',
      },
      {
        term: 'Voice of customer',
        means: 'Collecting what customers say, in their own words.',
        mistake: 'Founders rewrite what customers said into their own language, and lose the exact words that would have made the marketing work.',
      },
      {
        term: 'Segment',
        means: 'A group of customers who behave the same way for the same reason.',
        mistake: 'If two customers buy for different reasons, they are different segments — even if they look the same on paper.',
      },
    ],
  },

  {
    slug: 'growth',
    title: 'Growth and marketing numbers',
    blurb: 'What it costs to get a customer, and whether they stay.',
    terms: [
      {
        term: 'CAC (Customer Acquisition Cost)',
        means: 'Everything you spent on sales and marketing, divided by the number of new customers you got in that time.',
        mistake: "Founders count only the ad spend and leave out salaries. If someone's time went into winning that customer, their cost belongs here too.",
      },
      {
        term: 'Blended vs paid CAC',
        means: 'Blended counts every new customer. Paid counts only the ones you paid to get.',
        mistake: 'Blended looks great early, while word of mouth is doing the work. Track both, or you will not understand it when growth slows.',
      },
      {
        term: 'LTV / CLV (Lifetime Value)',
        means: 'The total profit one customer brings you over the whole time they stay.',
        mistake: 'Use profit, not revenue. LTV built on revenue is a made-up number, and in a services business it can be very wrong.',
      },
      {
        term: 'LTV:CAC ratio',
        means: 'How much value you get back for every rupee you spend winning a customer.',
        mistake: 'People repeat 3:1 as a rule. Treat it as a rough direction. It means nothing until you know how fast customers really leave.',
      },
      {
        term: 'CAC payback period',
        means: 'How many months of profit it takes to earn back what you spent getting that customer.',
        mistake: 'More useful than LTV:CAC when cash is tight. It tells you when the money comes back, not just whether it does.',
      },
      {
        term: 'Funnel',
        means: 'The steps a stranger goes through before becoming a customer.',
        mistake: 'Founders fix the middle. The real leaks are usually at the top, where you are talking to the wrong people, or at the bottom, where you never clearly ask for the sale.',
      },
      {
        term: 'Conversion rate',
        means: 'The share of people who move from one step to the next.',
        mistake: 'It means nothing without naming the steps. "20% conversion" from what, to what?',
      },
      {
        term: 'MQL / SQL',
        means: 'A lead marketing thinks is ready, and a lead sales agrees is ready.',
        mistake: 'Only useful if both sides agree what those words mean. Usually they do not, and deals get lost at that handover.',
      },
      {
        term: 'Lead',
        means: 'Anyone who has shown any interest at all.',
        mistake: 'This word causes more damage than any other here, because it makes someone downloading a PDF look like real demand.',
      },
      {
        term: 'Churn',
        means: 'How fast customers leave.',
        mistake: 'Count customers lost and money lost separately. Losing ten small customers and losing one big one are very different events.',
      },
      {
        term: 'Retention',
        means: 'The opposite of churn — who stays.',
        mistake: 'If the line flattens out, you have a real product. If it keeps falling to zero, you have a leaking bucket, and money spent on growth is wasted.',
      },
      {
        term: 'Cohort analysis',
        means: 'Grouping customers by the month they joined, then following each group over time.',
        mistake: 'The only honest way to see if the product is getting better. Totals hide a worsening product behind rising numbers.',
      },
      {
        term: 'Activation',
        means: 'The first moment a user actually gets value.',
        mistake: 'If you cannot name that moment, you cannot fix the way new users start.',
      },
      {
        term: 'North star metric',
        means: 'The one number that best shows you are delivering real value.',
        mistake: 'Choose one that only goes up when customers genuinely benefit. Choose badly and your whole team works on the wrong thing.',
      },
      {
        term: 'Vanity metric',
        means: 'A number that keeps going up and predicts nothing — page views, downloads, followers, signups.',
        mistake: 'Not useless, but never a reason to make a decision. If a number cannot fall when things go badly, it is not measuring anything.',
      },
      {
        term: 'ROAS',
        means: 'How much revenue each rupee of advertising brings in.',
        mistake: 'That is revenue, not profit. Good ROAS on a low-margin product can still lose you money.',
      },
      {
        term: 'CPL / CPA / CPC / CPM',
        means: 'Cost per lead, per customer, per click, and per thousand times your ad is shown.',
        mistake: 'Advertising words. Learn them so an agency cannot confuse you with them.',
      },
      {
        term: 'Attribution',
        means: 'Deciding which channel gets the credit for a sale.',
        mistake: 'Genuinely hard, and getting harder. Do not rebuild your plan around numbers you cannot check yourself.',
      },
      {
        term: 'K-factor / virality',
        means: 'How many new users each existing user brings in.',
        mistake: 'True viral growth is rare. Most growth called viral is paid growth with a referral scheme on top.',
      },
      {
        term: 'Organic vs paid',
        means: 'Visitors you earned, and visitors you paid for.',
        mistake: 'Organic looks free but is not. It costs time and content. Count that cost.',
      },
      {
        term: 'Top of funnel / bottom of funnel',
        means: 'Work that makes people aware of you, and work that closes sales.',
        mistake: 'Founders short of cash usually spend too much at the top, which is exactly where the money comes back slowest.',
      },
    ],
  },

  {
    slug: 'revenue',
    title: 'Revenue and repeat business',
    blurb: 'Which money counts as steady, and which only looks like it.',
    terms: [
      {
        term: 'MRR / ARR',
        means: 'Revenue that repeats every month, or every year.',
        mistake: 'Repeating means the contract says so. One-off projects and paid trials are not ARR, however much you want them to be.',
      },
      {
        term: 'ACV (Annual Contract Value)',
        means: "One customer's contract, counted for one year.",
        mistake: 'Do not mix it up with total contract value, which covers all the years together. Mixing them can multiply your numbers by three.',
      },
      {
        term: 'ARPU / ARPA',
        means: 'Average revenue per user, or per account.',
        mistake: 'One average across very different customers hides everything worth knowing. Split it up.',
      },
      {
        term: 'NRR / NDR (Net Revenue Retention)',
        means: 'Money from your existing customers this year compared with last year, counting upgrades and losses together.',
        mistake: 'Above 100% means you would still grow with no new customers. The 120% figure people quote comes from large enterprise software. Smaller businesses usually sit around 101–102%.',
      },
      {
        term: 'GRR (Gross Revenue Retention)',
        means: 'The same, but without counting upgrades. The honest number for what you are losing.',
        mistake: 'NRR can look healthy while GRR is bleeding, if a few accounts are growing fast. Look at both.',
      },
      {
        term: 'Expansion revenue',
        means: 'More money from customers you already have.',
        mistake: 'The cheapest revenue there is, and the one early founders ignore while chasing new names.',
      },
      {
        term: 'Gross margin',
        means: 'What is left from your revenue after the direct cost of delivering it, shown as a percentage.',
        mistake: 'The most telling number in a young business. A low gross margin limits everything you can afford to do later.',
      },
      {
        term: 'Contribution margin',
        means: 'Gross margin after the extra costs of serving that particular customer.',
        mistake: 'It tells you whether each new customer helps you or hurts you.',
      },
      {
        term: 'COGS',
        means: 'The direct cost of delivering — hosting, materials, the staff who do the work.',
        mistake: 'Founders put salaries in the wrong place, and then gross margin means nothing.',
      },
      {
        term: 'Rule of 40',
        means: 'Your growth rate plus your profit margin should add up to more than 40.',
        mistake: 'The person who wrote it meant it for large companies, roughly $50 million of revenue and above. Used on a ₹5 crore business it punishes exactly the steady, profitable businesses it was never about.',
      },
      {
        term: 'Burn multiple',
        means: 'How much cash you burn to add one rupee of repeating revenue.',
        mistake: 'A test of how carefully you use money. Lower is better. There is no trustworthy standard number to compare against.',
      },
      {
        term: 'Quick ratio (SaaS)',
        means: 'New and upgraded revenue, divided by lost and reduced revenue.',
        mistake: 'It shows whether growth is beating losses. The benchmark numbers people quote come from nowhere you can check.',
      },
      {
        term: 'Magic number',
        means: 'New repeating revenue, divided by what you spent on sales and marketing the period before.',
        mistake: 'A rough check on sales efficiency. People treat it as far more exact than it is.',
      },
      {
        term: 'GMV',
        means: 'The total value of everything sold through a marketplace.',
        mistake: 'This is not your revenue. Your revenue is your cut of it. Confusing the two is the classic marketplace exaggeration.',
      },
      {
        term: 'Take rate',
        means: 'Your percentage cut of what is sold.',
        mistake: 'The number that decides whether a marketplace is a business or a charity.',
      },
      {
        term: 'Revenue vs bookings vs collections',
        means: 'Money earned, contracts signed, and cash actually in the bank.',
        mistake: 'Three different numbers, often used as if they were one. Only the cash pays salaries.',
      },
    ],
  },

  {
    slug: 'cash',
    title: 'Cash and accounts',
    blurb: 'The difference between being profitable and being able to pay people.',
    terms: [
      {
        term: 'Unit economics',
        means: 'Whether one customer, one order or one project makes money after its direct costs.',
        mistake: 'If one loses money, doing more of them makes things worse, not better. This is the most skipped sum in early business.',
      },
      {
        term: 'Burn rate',
        means: 'Cash you use up each month. Gross burn is everything you spend. Net burn is spending minus income.',
        mistake: 'Founders quote gross burn to sound careful and net burn to sound safe. Ask which one you are being told.',
      },
      {
        term: 'Runway',
        means: 'How many months you can survive at your current net burn.',
        mistake: 'Work it out again every month. Runway based on last quarter, while you are hiring, is fiction.',
      },
      {
        term: 'Default alive / default dead',
        means: 'Whether you reach profit on the cash you already have, without raising again.',
        mistake: 'The most useful question a founder can ask themselves, and most cannot answer it.',
      },
      {
        term: 'Break-even',
        means: 'The point where income covers costs.',
        mistake: "Two different things: covering this month's costs, and paying back everything you have put in so far. Know which one you mean.",
      },
      {
        term: 'Working capital',
        means: 'Cash stuck in day-to-day running — stock, unpaid invoices, credit from suppliers.',
        mistake: 'Profitable businesses die here. Growing uses up cash, which is why growing fast can bankrupt you.',
      },
      {
        term: 'Cash conversion cycle',
        means: 'The number of days between paying for something and getting paid for it.',
        mistake: 'The real clock in any business holding stock or delivering services. Shortening it is often worth more than raising your prices.',
      },
      {
        term: 'DSO (Days Sales Outstanding)',
        means: 'How many days customers take to pay you, on average.',
        mistake: 'In Indian business and government work this is often 60 to 120 days. Plan for what happens, not for what the invoice says.',
      },
      {
        term: 'Accounts receivable / payable',
        means: 'Money owed to you, and money you owe.',
        mistake: 'An invoice is not cash. Never treat it as money in the bank.',
      },
      {
        term: 'EBITDA',
        means: 'Profit before interest, tax, and the cost of things wearing out.',
        mistake: 'A rough measure of how the business runs. It is not cash, and treating it as cash has closed real companies.',
      },
      {
        term: 'Cash flow vs profit',
        means: 'Profit is what the books say. Cash flow is what is in the bank.',
        mistake: 'You can be profitable and unable to pay anyone in the same month. Most first-time founders learn this the hard way.',
      },
      {
        term: 'Accrual vs cash accounting',
        means: 'Recording money when it is earned or owed, or only when it actually moves.',
        mistake: 'It changes what your profit and loss statement means. Find out which one your books use before you read them.',
      },
      {
        term: 'CapEx vs OpEx',
        means: 'One-off purchases of things you keep, and the regular cost of running.',
        mistake: 'It changes your tax, when cash leaves you, and how a bank sees you.',
      },
      {
        term: 'Fixed vs variable cost',
        means: 'Costs that stay the same whatever you sell, and costs that rise as you sell more.',
        mistake: 'They set your break-even point and decide how much a bad month hurts.',
      },
      {
        term: 'Operating leverage',
        means: 'How fast profit grows as sales grow, given your fixed costs.',
        mistake: 'Wonderful on the way up and brutal on the way down.',
      },
      {
        term: 'Depreciation / amortisation',
        means: 'Spreading the cost of something you bought across the years you use it.',
        mistake: 'This is why your profit statement and your bank balance never agree.',
      },
      {
        term: 'Bootstrapping',
        means: "Growing on your own money and your customers' money, instead of investors'.",
        mistake: 'A real strategy, not second best. It changes which numbers matter — how fast you get your money back matters more than lifetime value.',
      },
    ],
  },

  {
    slug: 'funding',
    title: 'Raising money and shares',
    blurb: 'The words in a term sheet, and which ones actually cost you.',
    terms: [
      {
        term: 'Pre-money / post-money valuation',
        means: 'What the company is worth before the new money goes in, and after. Post-money is pre-money plus the investment.',
        mistake: 'Founders agree a number without saying which one they mean, and lose several percent of the company doing it.',
      },
      {
        term: 'Dilution',
        means: 'Your share of the company getting smaller when new shares are created.',
        mistake: 'A smaller share of a bigger company is fine. A smaller share of the same company is not. Track it at every round.',
      },
      {
        term: 'Cap table',
        means: 'The list of who owns what.',
        mistake: 'Keep it clean and up to date from day one. A messy one kills more deals during checks than bad numbers do.',
      },
      {
        term: 'ESOP pool',
        means: 'Shares set aside for employees.',
        mistake: 'The trap: investors usually want the pool created before their money goes in, so the existing owners — mostly you — pay for it. Negotiate how big it is and when it is created.',
      },
      {
        term: 'Vesting / cliff',
        means: 'Earning your shares over time. The cliff is the waiting period before you earn any at all.',
        mistake: 'Founders should vest too. Splitting shares between co-founders with no vesting is the most common cause of serious early fights.',
      },
      {
        term: 'Term sheet',
        means: 'A short summary of the main terms of an investment. It does not bind anyone yet.',
        mistake: 'Everyone reads the money terms. The control terms decide how you will live. Read those more carefully.',
      },
      {
        term: 'Priced round',
        means: 'A round where you agree what the company is worth and issue shares now.',
        mistake: 'The other option is to delay agreeing a value, using an instrument that converts later.',
      },
      {
        term: 'Convertible note',
        means: 'A loan that turns into shares at a later round.',
        mistake: 'In India these come under FEMA rules, with special conditions for foreign investors. Get advice before using one across borders.',
      },
      {
        term: 'SAFE / iSAFE',
        means: 'Money now, shares later. No interest and no repayment date. The Indian version is usually called an iSAFE.',
        mistake: 'Popular because it is fast. Signing several without working out the final dilution is a very common and very expensive mistake.',
      },
      {
        term: 'CCPS / CCD',
        means: 'The standard Indian instruments used when institutional investors put money in at an agreed valuation.',
        mistake: 'Indian investors often prefer these to plain shares because of the extra rights attached. Understand what those rights let them do.',
      },
      {
        term: 'Valuation cap / discount',
        means: 'Limits on the price at which a note or SAFE turns into shares, protecting the early investor.',
        mistake: 'The cap usually ends up becoming the valuation. Set it as if it were one.',
      },
      {
        term: 'Liquidation preference',
        means: 'Who gets paid first when the company is sold, and how much.',
        mistake: '"1x non-participating" is the founder-friendly version. "Participating" means investors get their money back and a share of the rest — on a small sale you can walk away with almost nothing.',
      },
      {
        term: 'Participating vs non-participating',
        means: 'Whether the investor gets paid twice when the company is sold.',
        mistake: 'This can be worth more than several crore of valuation, and most first-time founders never check it.',
      },
      {
        term: 'Anti-dilution',
        means: 'Protection for investors if you later raise money at a lower price.',
        mistake: '"Full ratchet" is harsh. "Broad-based weighted average" is normal. Know which one you signed.',
      },
      {
        term: 'Pro-rata rights',
        means: "An investor's right to keep their percentage by investing again in later rounds.",
        mistake: 'Fair to give. Just remember it takes space away from future investors.',
      },
      {
        term: 'Down round',
        means: 'Raising money at a lower value than last time.',
        mistake: 'You can survive it, but it triggers anti-dilution and hurts the team. Usually caused by raising too high, too early.',
      },
      {
        term: 'Bridge round',
        means: 'Money to get you from one proper round to the next.',
        mistake: 'Ask honestly what it is getting you to. If there is nothing waiting on the other side, it is not a bridge.',
      },
      {
        term: 'Runway-to-milestone',
        means: 'Raising enough to reach a specific proof point, not just to stay alive.',
        mistake: '"Eighteen months of runway" with no goal attached is just panic postponed.',
      },
      {
        term: 'Lead investor',
        means: 'The investor who sets the terms and puts in the biggest cheque.',
        mistake: 'Without one, a round rarely closes. Chasing ten small cheques with no lead wastes months.',
      },
      {
        term: 'Due diligence',
        means: 'The investor checking everything — legal, financial, technical, and calling your customers.',
        mistake: 'Clean books and contracts make this quick. A mess can kill the deal.',
      },
      {
        term: 'Data room',
        means: 'The organised folder of documents investors read.',
        mistake: 'Build it before you start raising, not during.',
      },
      {
        term: 'Drag-along / tag-along',
        means: 'The majority can force the minority to sell. The minority can join a sale by the majority.',
        mistake: 'Normal terms, but read the thresholds carefully.',
      },
      {
        term: 'Board seat / observer',
        means: 'A vote in how the company is run, or the right to attend without a vote.',
        mistake: 'Who sits on your board matters more than any single term in the paperwork.',
      },
      {
        term: 'Secondary',
        means: 'Selling shares you already own, instead of creating new ones.',
        mistake: 'This is how founders take some money out. Usually not allowed until later rounds.',
      },
      {
        term: 'Angel / pre-seed / seed / Series A',
        means: 'Rough names for the stages of raising money.',
        mistake: 'The names have drifted a lot. What matters is the proof expected at each stage, not what it is called.',
      },
      {
        term: 'Venture debt',
        means: 'A loan for companies that already have investors.',
        mistake: 'It does not cost you shares, but it is still a loan. It has conditions, and it must be repaid whatever happens.',
      },
      {
        term: 'Revenue-based financing',
        means: 'Money you repay as a share of your monthly revenue.',
        mistake: 'Useful when revenue is steady. Expensive if growth stops.',
      },
      {
        term: 'Grant / subsidy',
        means: 'Government or institutional money you do not repay and do not give shares for.',
        mistake: 'Slow and full of paperwork, and genuinely free. Indian founders apply for far too few of these.',
      },
    ],
  },

  {
    slug: 'sales',
    title: 'Selling',
    blurb: 'How a deal really moves, and how to tell a real one from a polite one.',
    terms: [
      {
        term: 'Pipeline',
        means: 'All the live deals you are working on, with their stage and value.',
        mistake: 'A pipeline with no defined stages and no next dates is a wish list.',
      },
      {
        term: 'Sales cycle',
        means: 'How long it takes from the first conversation to a signed contract.',
        mistake: 'Six to twelve months is normal for large companies. Founders without funding regularly underestimate this and run out of cash halfway through.',
      },
      {
        term: 'Discovery call',
        means: 'The call where you learn about the customer before you pitch anything.',
        mistake: 'If you spoke more than they did, it was not discovery.',
      },
      {
        term: 'Qualification (BANT / MEDDIC)',
        means: 'Ways of checking whether a deal is real. Is there budget, is this the person who decides, is the need real, is there a date.',
        mistake: 'Founders skip this because every conversation feels precious. Then they spend six months on a deal that never had any budget.',
      },
      {
        term: 'Champion',
        means: 'The person inside the customer who wants this and will argue for it.',
        mistake: 'No champion, no deal. Someone friendly is not a champion. A champion spends their own reputation on you.',
      },
      {
        term: 'Economic buyer',
        means: 'The person who can actually release the money.',
        mistake: 'Often not the person you have been talking to.',
      },
      {
        term: 'POC / pilot',
        means: 'A short trial before a full purchase.',
        mistake: 'A real pilot has a budget, a business owner involved, agreed measures of success, and a clear route to buying if it works. Without those four it is theatre, and it will eat three months.',
      },
      {
        term: 'Land and expand',
        means: 'Win a small deal first, then grow inside that customer.',
        mistake: 'It works because the hard parts — paperwork, security checks, setup — only have to be done once, however small the first deal.',
      },
      {
        term: 'PLG vs SLG',
        means: 'Customers try the product and then buy, or a salesperson sells it to them.',
        mistake: 'Not a matter of taste. Your price, your buyer, and how obvious the value is decide it for you.',
      },
      {
        term: 'Inbound / outbound',
        means: 'Customers find you, or you go and find them.',
        mistake: 'Inbound takes longer to build and costs less to run. Outbound is the opposite. Most early companies need both.',
      },
      {
        term: 'SDR / AE / CSM',
        means: 'One person books meetings, one closes deals, one keeps customers happy and growing.',
        mistake: 'Splitting these into three jobs too early is a classic over-hire. The founder does all three until the process is proven.',
      },
      {
        term: 'Win rate',
        means: 'Deals won, out of deals you seriously chased.',
        mistake: 'A low win rate with a lot of activity usually means you are chasing the wrong people, not working too little.',
      },
      {
        term: 'Free trial vs freemium',
        means: 'Full access for a limited time, or a limited version that is free forever.',
        mistake: 'Very different economics. Free forever works for consumers. It usually fails when the buyer needs security, compliance and control.',
      },
      {
        term: 'Discount / price integrity',
        means: 'Cutting your price to close the deal.',
        mistake: "Every discount teaches the customer what you are really worth, and next year's price starts from there.",
      },
      {
        term: 'RFP / tender',
        means: 'A formal buying process, common in government and large companies.',
        mistake: "If you did not help write the requirements, you are usually there to make someone else's bid look competitive.",
      },
      {
        term: 'MSA / SOW / NDA / LOI',
        means: 'Master agreement, description of the work, confidentiality agreement, letter of intent.',
        mistake: 'A letter of intent is not revenue. An NDA is not a commitment. Know which document actually binds anyone.',
      },
      {
        term: 'Procurement / vendor onboarding',
        means: "The customer's own buying and approval process.",
        mistake: 'For a small supplier this is often the longest part of the sale. Plan in months, not weeks.',
      },
      {
        term: 'Reference customer',
        means: 'A customer willing to speak for you publicly.',
        mistake: 'The most valuable thing you can have when selling to large companies, and the thing founders forget to ask for while the customer is still happy.',
      },
      {
        term: 'Channel partner / reseller',
        means: 'Someone who sells on your behalf.',
        mistake: 'Rarely works before you can sell it yourself. Partners make a working process bigger. They do not create one.',
      },
    ],
  },

  {
    slug: 'product',
    title: 'Product and delivery',
    blurb: 'Building the right thing, and finishing it without losing money.',
    terms: [
      {
        term: 'MVP',
        means: 'The smallest thing you can build to test the belief most likely to be wrong.',
        mistake: 'It is not "version one, but worse". If it does not test a belief, it is just unfinished.',
      },
      {
        term: 'Riskiest assumption test',
        means: 'Deliberately testing the belief that would kill the business if it turned out to be wrong.',
        mistake: 'Often a better idea than an MVP, because it forces you to say out loud what the risk actually is.',
      },
      {
        term: 'Iteration / build-measure-learn',
        means: 'Short cycles of building something, watching what happens, and changing it.',
        mistake: 'The cycle only works if you decide beforehand what result would change your mind.',
      },
      {
        term: 'Roadmap',
        means: 'The order in which you plan to build things.',
        mistake: 'A roadmap that never changes is not listening to customers. One that changes every week is not a plan.',
      },
      {
        term: 'Backlog',
        means: 'The queue of things not built yet.',
        mistake: 'It grows forever. The skill is deleting things, not ordering them.',
      },
      {
        term: 'Scope creep',
        means: 'The work quietly growing after you agreed the price.',
        mistake: 'The main reason services and project businesses lose money.',
      },
      {
        term: 'Technical debt',
        means: 'Shortcuts taken now that cost more later.',
        mistake: 'Sometimes the right choice, made on purpose. Dangerous when it happens by accident and nobody writes it down.',
      },
      {
        term: 'SLA / uptime',
        means: 'A promise in the contract about how reliable your service will be.',
        mistake: 'Large customers ask early. Promising 99.9% without knowing what that costs you to deliver is a trap.',
      },
      {
        term: 'Feature vs product vs company',
        means: 'One useful thing, a whole thing someone buys, and a repeatable business built around it.',
        mistake: 'Many startups are features. Useful, but they cannot hold up a company on their own.',
      },
      {
        term: 'Customisation vs configuration',
        means: 'Building something special for one customer, or letting them change settings themselves.',
        mistake: 'Building something special feels like a win and quietly destroys your ability to sell the same thing again.',
      },
    ],
  },

  {
    slug: 'people',
    title: 'People and hiring',
    blurb: 'Hiring, delegating, and the paperwork that protects you.',
    terms: [
      {
        term: 'Scorecard (hiring)',
        means: 'A written list of what the person in this role must actually achieve, agreed before you start interviewing.',
        mistake: 'Most hiring runs on a list of duties, which predicts nothing. Results predict.',
      },
      {
        term: 'Structured interview',
        means: 'The same questions, in the same order, scored the same way, for every candidate.',
        mistake: 'Far better at predicting who will do well than a free conversation, and almost nobody does it.',
      },
      {
        term: 'Reference check',
        means: 'Talking to people who actually worked with the candidate.',
        mistake: 'The most skipped and most useful step in hiring. Ask what the person did, not what they were like.',
      },
      {
        term: 'Ramp time',
        means: 'How long a new person takes to become useful.',
        mistake: 'For senior roles, expect nine to twelve months. The skill is noticing when someone is not getting there.',
      },
      {
        term: 'Span of control',
        means: 'How many people report to one manager.',
        mistake: 'Past about seven, you stop being able to actually manage them. That is a structure problem, not a personal failing.',
      },
      {
        term: 'Founder-led everything',
        means: 'The stage where you personally do sales, hiring, support and product.',
        mistake: 'Right at the start. It becomes the thing holding the whole business back at a predictable point, usually between fifteen and thirty people.',
      },
      {
        term: 'Delegation vs abdication',
        means: 'Handing over a decision with context and accountability, or just dropping it on someone.',
        mistake: 'Founders swing between the two. Real delegation means allowing them the same room to make mistakes that you allow yourself.',
      },
      {
        term: 'Attrition',
        means: 'How fast employees leave.',
        mistake: 'Separate the people you wanted to keep from the people you did not. Some leaving is the system working.',
      },
      {
        term: 'PIP (Performance Improvement Plan)',
        means: 'A written process to help someone improve before you let them go.',
        mistake: 'In India the paperwork matters legally. Handle exits properly, or they become expensive.',
      },
      {
        term: 'Contractor vs employee',
        means: 'Two different sets of legal, tax and benefit obligations.',
        mistake: 'Calling an employee a contractor to save money creates real risk. Get it right from the start.',
      },
      {
        term: 'ESOP (employee)',
        means: 'Share options given to staff.',
        mistake: 'Only motivating if the person understands the price, the waiting period, what it costs to buy them, and the tax. An unexplained ESOP keeps nobody.',
      },
      {
        term: 'Sweat equity',
        means: 'Shares given for work instead of cash.',
        mistake: 'Regulated in India, with limits and a proper process. Never do it on a handshake.',
      },
      {
        term: 'Founder agreement / co-founder split',
        means: 'The written terms between founders — shares, roles, vesting, and what happens if someone leaves.',
        mistake: 'The most important document you will avoid writing. Write it while everyone still likes each other.',
      },
      {
        term: 'POSH compliance',
        means: "A legal requirement under India's law on sexual harassment at work.",
        mistake: 'Compulsory once you pass the employee limit, including setting up an Internal Committee. Small firms miss it constantly.',
      },
      {
        term: 'Culture',
        means: 'The behaviour that actually gets rewarded and allowed.',
        mistake: 'Not the values printed on the wall. It is what you do when your best performer behaves badly.',
      },
    ],
  },

  {
    slug: 'strategy',
    title: 'Strategy and competition',
    blurb: 'Why you win, why you lose, and the thinking traps in between.',
    terms: [
      {
        term: 'Moat',
        means: 'A structural reason a competitor cannot easily take your customers.',
        mistake: 'Being better is not a moat. Being hard to leave is.',
      },
      {
        term: 'Switching cost',
        means: 'What it costs a customer to leave you — money, data, retraining, risk.',
        mistake: 'Often the only real protection a small business can build. Design for it on purpose.',
      },
      {
        term: 'Network effect',
        means: 'The product gets more useful as more people use it.',
        mistake: 'Genuinely rare. Most claimed network effects are just size.',
      },
      {
        term: 'Economies of scale',
        means: 'The cost of each unit falls as you make more of them.',
        mistake: 'Real in manufacturing, weaker in services, and sometimes not there at all.',
      },
      {
        term: 'Differentiation',
        means: 'A difference the customer can see, and cares about.',
        mistake: 'If they cannot see it, it does not exist commercially, however real it is technically.',
      },
      {
        term: 'Commoditisation',
        means: 'When all the options look the same and only price matters.',
        mistake: 'Every market ends up here eventually. Set your prices today as if it is coming.',
      },
      {
        term: 'Parity tax',
        means: 'Having to rebuild the boring features the big player already has, before anyone cares about what makes you different.',
        mistake: 'You pay this when replacing someone. You do not when the customer is starting fresh. Budget for it.',
      },
      {
        term: 'First-mover advantage',
        means: 'Being first into a market.',
        mistake: 'Overrated, and often the opposite. The ones who come next learn from your expensive mistakes.',
      },
      {
        term: 'Incumbent',
        means: 'The established player already in your market.',
        mistake: 'Their weakness is rarely the product. It is usually the business model or the costs they cannot walk away from.',
      },
      {
        term: 'Counter-positioning',
        means: 'Using a business model the big player cannot copy without damaging what they already have.',
        mistake: 'The most reliable way for a small company to beat a large one.',
      },
      {
        term: 'Vertical vs horizontal',
        means: 'Serving one industry deeply, or doing one job for many industries.',
        mistake: 'For Indian SMEs, going deep in one industry is often the advantage, because relationships inside one sector build on each other.',
      },
      {
        term: 'Opportunity cost',
        means: 'The value of the best thing you gave up in order to do this.',
        mistake: 'It is in every decision you make, and it never appears in your accounts.',
      },
      {
        term: 'Two-way vs one-way door',
        means: 'Decisions you can undo, and decisions you cannot.',
        mistake: 'Moving fast is right for the ones you can undo, and reckless for the ones you cannot. Most founders use one speed for both.',
      },
      {
        term: 'Sunk cost fallacy',
        means: 'Carrying on because of what you have already spent.',
        mistake: 'The most expensive habit in business. Money and years already gone tell you nothing about the future.',
      },
      {
        term: 'Survivorship bias',
        means: 'Learning only from the ones who made it.',
        mistake: 'Why most business books mislead. The people who failed did many of the same things. Nobody wrote their story down.',
      },
      {
        term: "Goodhart's law",
        means: 'Once a measurement becomes a target, it stops being a good measurement.',
        mistake: 'Give a team a number and they will hit it — sometimes by damaging the thing you actually wanted.',
      },
      {
        term: 'Confirmation bias',
        means: 'Looking for evidence that you were right.',
        mistake: 'Especially dangerous in customer conversations, where founders ask questions designed to get a yes.',
      },
    ],
  },

  {
    slug: 'india',
    title: 'India: legal, tax and compliance',
    blurb: 'The registrations, filings and deadlines nobody tells you about.',
    /* Displayed, not filed. Every fact in this section was verified on one day
       and several have already moved once inside a year. A founder reading a
       stale rate here would be relying on us for it. */
    note: 'Checked on 29 August 2026. These rules change often — GST rates, MSME limits and the DPDP dates have all moved within a year. Please confirm anything here before acting on it.',
    terms: [
      {
        term: 'Pvt Ltd / LLP / OPC / sole proprietorship',
        means: 'The main types of business you can register in India.',
        mistake: 'Your choice affects tax, whether you can raise money, how much paperwork you carry, and whether your personal assets are at risk. In practice investors only fund a Pvt Ltd. The rules forcing an OPC to convert were removed in 2021, and many websites still say otherwise.',
      },
      {
        term: 'CIN / DIN / PAN / TAN',
        means: 'Company number, director number, tax number, and tax-deduction number.',
        mistake: 'Basic identity numbers you will be asked for again and again.',
      },
      {
        term: 'MOA / AOA',
        means: 'The two founding documents that say what the company is and how it is run.',
        mistake: 'The AOA controls who can sell shares and who decides what. Investors will want it changed — read what changes.',
      },
      {
        term: 'ROC / MCA filings',
        means: 'The yearly filings every company must make with the Registrar of Companies.',
        mistake: 'Not optional, and there are penalties. Late fees add up fast.',
      },
      {
        term: 'DIR-3 KYC',
        means: 'The identity filing that every company director has to make.',
        mistake: 'Now once every three years, due 30 June, from 31 March 2026 — no longer every year by 30 September. Your cycle depends on the year your director number was issued.',
      },
      {
        term: 'DPIIT recognition / Startup India',
        means: 'Official government recognition as a startup, which unlocks certain benefits.',
        mistake: 'The rules changed in February 2026 — the turnover limit went up to ₹200 crore, and a deep-tech category was added at 20 years and ₹300 crore. Most guides online are out of date.',
      },
      {
        term: 'Section 80-IAC',
        means: 'A tax holiday for startups that have DPIIT recognition.',
        mistake: 'A new Income-tax Act replaced the old one on 1 April 2026. The rates did not change but the section numbers did — this is now section 140.',
      },
      {
        term: 'Angel tax',
        means: 'Tax on money you raised above the assessed value of your shares, from Indian investors.',
        mistake: 'Removed from AY 2025-26, which is FY 2024-25. Often reported a year out, including in decks still being sent around.',
      },
      {
        term: 'GST / GSTIN',
        means: 'The tax on goods and services, and your registration number for it.',
        mistake: 'The rates are now 5, 18 and 40, plus zero, since 22 September 2025. The 12% and 28% rates were removed.',
      },
      {
        term: 'ITC (Input Tax Credit)',
        means: 'Using the GST you paid on purchases to reduce the GST you owe.',
        mistake: 'Two things quietly cancel the benefit: some purchases are blocked, and suppliers who do not file properly.',
      },
      {
        term: 'LUT (Letter of Undertaking)',
        means: 'A form that lets an exporter supply without paying IGST upfront.',
        mistake: 'Important if you export services. It is about cash flow, not about paperwork.',
      },
      {
        term: 'RCM (Reverse Charge Mechanism)',
        means: 'The buyer pays the GST instead of the seller.',
        mistake: 'It applies to many services bought from abroad. One rule about intermediaries was removed from 30 March 2026, which changed things for Indian firms serving foreign clients.',
      },
      {
        term: 'TDS',
        means: 'Tax your customer takes out of your payment and sends to the government on your behalf.',
        mistake: 'It affects your cash flow, and matching it all up at the year end is real work.',
      },
      {
        term: 'MSME / Udyam registration',
        means: 'Registering as a micro, small or medium business.',
        mistake: 'The limits changed on 1 April 2025: micro is ₹2.5 crore investment and ₹10 crore turnover; small is ₹25 crore and ₹100 crore; medium is ₹125 crore and ₹500 crore. The 45-day payment rule gives you real power over large customers — but only if you are micro or small, and not if you are a trader.',
      },
      {
        term: 'DPDP Act / Rules',
        means: "India's data protection law.",
        mistake: 'The rules came in November 2025 and arrive in stages — consent managers around November 2026, the main duties around May 2027. The older IT Act rules still apply until then, so there is no gap where nothing applies.',
      },
      {
        term: 'FSSAI licence',
        means: 'The licence you need to run a food business.',
        mistake: 'Turnover bands went up on 1 April 2026 and renewal was removed, so the licence now lasts indefinitely. But the yearly fee stayed, and not paying it suspends you automatically. Anyone selling food online, and any brand owner’s head office, needs a Central Licence at any turnover — so most direct-to-consumer brands get no relief. The brand owner is fully responsible and cannot pass the blame to the factory.',
      },
      {
        term: 'EPF / ESI',
        means: 'Compulsory provident fund and employee insurance.',
        mistake: 'The wage limits of ₹15,000 and ₹21,000 had not changed as of August 2026, despite a lot of news saying otherwise. They can now be changed by notification alone, so they could move quickly.',
      },
      {
        term: 'Labour Codes',
        means: "Four laws that combine India's older labour laws into one set.",
        mistake: 'In force since 21 November 2025, but most of the detailed rules have not been issued yet, so practice is still settling.',
      },
      {
        term: 'FEMA / FDI / ODI',
        means: 'The rules for money coming into India from abroad, and going out.',
        mistake: 'Any foreign investor, foreign subsidiary or overseas holding company brings these in. Get advice before, not after.',
      },
      {
        term: 'FIRC',
        means: 'A certificate proving you received money from abroad.',
        mistake: 'You need it for export benefits, and when investors check your books.',
      },
      {
        term: 'SISFS (Startup India Seed Fund Scheme)',
        means: 'Government seed money, given out through approved incubators.',
        mistake: 'Cheap or free money that Indian founders apply for far too rarely.',
      },
      {
        term: 'Incubator / accelerator',
        means: 'Long-term support and space, or a fixed-length programme usually taken in exchange for shares.',
        mistake: 'Two different things, often confused. Judge either one on the people it actually introduces you to, not on its name.',
      },
    ],
  },
];

/** Every term, counted once — used for the heading and the search count. */
export const GLOSSARY_TERM_COUNT = GLOSSARY.reduce((n, s) => n + s.terms.length, 0);
