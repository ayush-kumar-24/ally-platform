/**
 * data/watch.js — the three tabs under "Things to watch".
 *
 * NO DESCRIPTIONS, BY DECISION -- NOT BY OMISSION. Written descriptions for all
 * thirty do exist (ally-podcast-episodes-annotated.md, 7 Sep 2026), but they
 * were written for the RAG corpus: they say what a chunk contributes to Ally's
 * diagnosis, and several read as internal notes rather than as a
 * recommendation. Aarya looked at the cards without them on 8 Sep and kept them
 * that way. The titles carry it -- "He spent $0 on marketing for 2 years, then
 * raised $400M" needs no help from us.
 *
 * So every field here is a fact off the source list: title, show, host where
 * credited, publish date. If somebody later writes a founder-facing line for
 * one, add a `why`; the card renders it when present and looks right without.
 *
 * LINKS GO TO SOMEWHERE A FOUNDER CAN LISTEN, which is not always the same URL
 * the transcript came from. Where the source list gave both a publisher page
 * and a transcript mirror, the publisher wins.
 *
 * TWO EPISODES HAVE NO PINNED URL (Max Hodak, and Founders #430 on Claude
 * Hopkins). The source list flags both: one is mirrored under three different
 * titles, the other resolves to a different, earlier episode. They link to
 * their show index instead and say so, because sending a founder to the wrong
 * episode is worse than sending them one click short of the right one.
 */

/** Episodes. Ordered newest first -- the list is a rotation, not a ranking. */
export const PODCASTS = [
  {
    id: 'pg-startups-ambition',
    title: 'Paul Graham on Startups, Ambition, and Great Founders',
    by: 'YC Startup Podcast · host Vivian Shen',
    when: '5 Sep 2026',
    url: 'https://podscripts.co/podcasts/y-combinator-startup-podcast/paul-graham-on-startups-ambition-and-great-founders',
  },
  {
    id: 'broshi-notch',
    title: 'He fired almost everyone, kept 2 engineers, then grew 12x and raised a $30M Series A',
    by: 'A Product Market Fit Show · Rafael Broshi, Notch',
    when: '3 Aug 2026',
    url: 'https://pmfshow.buzzsprout.com/1889238/episodes/19558138-he-fired-almost-everyone-kept-2-engineers-then-grew-12x-and-raised-a-30m-series-a-rafael-broshi-co-founder-of-notch',
  },
  {
    id: 'jain-egnyte',
    title: 'How $6K in SEM Launched an Enterprise Sales Machine',
    by: 'The SaaS Podcast · Vineet Jain, Egnyte',
    url: 'https://saasclub.io/podcast/enterprise-sales-vineet-jain-egnyte/',
  },
  {
    id: 'steinberger-let-it-cook',
    title: 'What Happens When Everyone Lets It Cook',
    by: 'YC Root Access · Peter Steinberger',
    when: '10 Aug 2026',
    url: 'https://www.youtube.com/watch?v=whcfSGN6CAU',
  },
  {
    id: 'a16z-sell-ai',
    title: 'The Two Ways to Sell AI: Lighthouse or Landgrab?',
    by: 'a16z Podcast · Elena Burger, Joe Schmidt, Andy McCall',
    when: '13 Aug 2026',
    url: 'https://podscripts.co/podcasts/a16z-podcast/the-two-ways-to-sell-ai-lighthouse-or-landgrab',
  },
  {
    id: 'andreessen-founder-mindset',
    title: 'Marc Andreessen on the Mindset of Great Founders',
    by: 'a16z Podcast · with David Senra',
    when: '15 Mar 2026',
    url: 'https://a16z.com/podcast/marc-andreessen-on-the-mindset-of-great-founders-with-david-senra/',
  },
  {
    id: 'dulianinov-bright-machines',
    title: 'How AI & Robotics Are Reshoring Data Center Hardware',
    by: 'Startup Project #127 · Sviat Dulianinov, Bright Machines',
    when: '15 Aug 2026',
    url: 'https://thestartupproject.io/transcripts/sviat-dulianinov-bright-machines-ai-manufacturing',
  },
  {
    id: 'deming-founder-mindset',
    title: 'Dissecting the Founder Mindset',
    by: 'The Founder Mindset · David Deming & Reza Satchu',
    when: '1 Jul 2026',
    url: 'https://www.hbs.edu/foundry/podcast/dissecting-the-founder-mindset-david-deming',
  },
  {
    id: 'lund-templafy',
    title: 'He Closed a Global Enterprise Deal With No Product',
    by: 'The SaaS Podcast · Christian Lund, Templafy',
    url: 'https://saasclub.io/podcast/enterprise-sales-christian-lund-templafy/',
  },
  {
    id: 'fialkow-general-catalyst',
    title: "Oscar-Winner, Billionaire, Venture Capitalist: Inside David Fialkow's Mind",
    by: 'The Founder Mindset · David Fialkow, General Catalyst',
    when: '12 Aug 2026',
    url: 'https://www.hbs.edu/foundry/podcast/inside-david-fialkows-mind',
  },
  {
    id: 'shaam-omio',
    title: "From India to Harvard and Beyond: Naren Shaam's Unicorn Journey",
    by: 'The Founder Mindset · Naren Shaam, Omio',
    when: '29 Jul 2026',
    url: 'https://www.hbs.edu/foundry/podcast/from-india-to-harvard-and-beyond-naren-shaam',
  },
  {
    id: 'knudtson-workshop',
    title: 'The Complaint He Ignored for 9 Months Led to His First $10M',
    by: 'The SaaS Podcast · Rick Knudtson, Workshop',
    url: 'https://saasclub.io/podcast/listening-to-customers-rick-knudtson-workshop/',
  },
  {
    id: 'sfrou-848',
    title: 'What Liquid Death Can Teach Us About B2B SaaS',
    by: 'Startups For the Rest of Us #848 · Rob Walling',
    when: '1 Sep 2026',
    url: 'https://www.startupsfortherestofus.com/episodes/episode-848-what-liquid-death-can-teach-us-about-b2b-saas-rob-solo',
  },
  {
    id: 'altman-openai',
    title: 'Sam Altman on Building OpenAI & Betting on the Impossible',
    by: 'David Senra · Sam Altman',
    when: '23 Aug 2026',
    url: 'https://www.davidsenra.com/episode/sam-altman',
  },
  {
    id: 'asthana-postman',
    title: 'From Side Project to 40M Developers',
    by: 'Startup Project #128 · Abhinav Asthana, Postman',
    when: '26 Aug 2026',
    url: 'https://thestartupproject.io/transcripts/abhinav-asthana-postman-api-platform',
  },
  {
    id: 'sfrou-845',
    title: 'Lifetime Deals Revisited, Building is Not the Hard Part',
    by: 'Startups For the Rest of Us #845 · Rob Walling',
    when: '11 Aug 2026',
    url: 'https://www.startupsfortherestofus.com/episodes/episode-845-lifetime-deals-revisited-building-is-not-the-hard-part-and-confirming-an-idea-is-worth-paying-for-rob-solo',
  },
  {
    id: 'zima-omni',
    title: 'He lost all 5 of his first deals, then built the next Looker and raised $250M',
    by: 'A Product Market Fit Show · Colin Zima, Omni',
    when: '10 Aug 2026',
    url: 'https://pmfshow.buzzsprout.com/1889238/episodes/19584471-he-lost-all-5-of-his-first-deals-then-built-the-next-looker-and-raised-250m-colin-zima-co-founder-of-omni',
  },
  {
    id: 'zatlyn-cloudflare',
    title: 'Back at HBS: The Story Behind a Silicon Valley Unicorn',
    by: 'The Founder Mindset · Michelle Zatlyn, Cloudflare',
    when: '27 Aug 2026',
    url: 'https://www.hbs.edu/foundry/podcast/michellezatlyn',
  },
  {
    id: 'antos-within',
    title: 'He sold his 8-figure business to bet on a side app, then grew it 20x in a year',
    by: 'A Product Market Fit Show · Andrew Antos, Within',
    when: '31 Aug 2026',
    url: 'https://pmfshow.buzzsprout.com/1889238/episodes/19670056-he-sold-his-8-figure-business-to-bet-on-a-side-app-then-grew-it-to-20x-in-a-year-andrew-antos-co-founder-ceo-of-within',
  },
  {
    id: 'sfrou-846',
    title: 'Snail Mail, Cold Calling, Regulating Your Nervous System',
    by: 'Startups For the Rest of Us #846 · Rob Walling',
    when: '18 Aug 2026',
    url: 'https://www.startupsfortherestofus.com/episodes/episode-846-snail-mail-cold-calling-regulating-your-nervous-system-and-more-listener-questions-rob-solo',
  },
  {
    id: 'founders-430-hopkins',
    title: 'Founders #430 — How to Write Ads That Sell (Claude Hopkins)',
    by: 'Founders · David Senra',
    when: '23 Aug 2026',
    // The episode URL could not be pinned: a search resolves to the earlier
    // #207 Hopkins episode, which is a different episode. Series index instead.
    note: 'Episode link unconfirmed — opens the Founders series index.',
    url: 'https://colossus.com/series/founders/',
  },
  {
    id: 'junestrand-legora',
    title: 'You Need The Willingness To Learn Faster Than Anyone Else',
    by: 'YC Startup Podcast · Max Junestrand, Legora',
    when: '29 Aug 2026',
    url: 'https://podscripts.co/podcasts/y-combinator-startup-podcast/max-junestrand-you-need-the-willingness-to-learn-faster-than-anyone-else',
  },
  {
    id: 'korfgen-uplane',
    title: 'He Sold the Software Before He Built It. $1M ARR in 6 Months',
    by: 'The SaaS Podcast #492 · Julius Körfgen, Uplane',
    when: '27 Aug 2026',
    url: 'https://saasclub.io/podcast/selling-before-building-julius-korfgen-uplane/',
  },
  {
    id: 'founders-428-shannon',
    title: 'Founders #428 — How Claude Shannon Worked',
    by: 'Founders · David Senra',
    when: '9 Aug 2026',
    url: 'https://colossus.com/episode/428-how-claude-shannon-worked/',
  },
  {
    id: 'lindgren-endra',
    title: 'He spent $150K on brand before a product, then closed $1.5M ARR in 1 month',
    by: 'A Product Market Fit Show · Niklas Lindgren, Endra',
    when: '17 Aug 2026',
    url: 'https://pmfshow.buzzsprout.com/1889238/episodes/19638074-he-spent-150k-on-brand-before-he-had-a-product-then-closed-1-5m-arr-in-1-month-niklas-lindgren-co-founder-ceo-of-endra',
  },
  {
    id: 'loiacono-judi-health',
    title: 'He spent $0 on marketing for 2 years, then raised $400M at a $3.25B valuation',
    by: 'A Product Market Fit Show · AJ Loiacono, Judi Health',
    when: '24 Aug 2026',
    url: 'https://pmfshow.buzzsprout.com/1889238/episodes/19670005-he-spent-0-on-marketing-for-2-years-then-raised-400m-at-a-3-25b-valuation-aj-loiacono-co-founder-ceo-of-judi-health',
  },
  {
    id: 'tan-own-your-intelligence',
    title: 'Own Your Intelligence',
    by: 'YC Root Access · Garry Tan',
    when: '6 Aug 2026',
    url: 'https://www.ycombinator.com/library/WX-garry-tan-own-your-intelligence',
  },
  {
    id: 'sfrou-847',
    title: 'What Second Time Founders Do Differently, Pricing AI Agents',
    by: 'Startups For the Rest of Us #847 · Rob Walling',
    when: '25 Aug 2026',
    url: 'https://www.startupsfortherestofus.com/episodes/episode-847-what-second-time-founders-do-differently-pricing-ai-agents-and-more-listener-questions-rob-solo',
  },
  {
    id: 'hodak-no-blanket-rules',
    title: 'There Are No Blanket Rules',
    by: 'YC Startup Podcast · Max Hodak',
    when: '7 Aug 2026',
    // Mirrored under at least three different titles, so no single episode URL
    // resolves cleanly. Show page instead.
    note: 'Episode link unconfirmed — opens the show page.',
    url: 'https://podcasts.apple.com/us/podcast/y-combinator-startup-podcast/id1236907421',
  },
  {
    id: 'collison-what-if-you-succeed',
    title: 'What If You Succeed?',
    by: 'YC Startup Podcast · Patrick Collison',
    when: '31 Jul 2026',
    url: 'https://www.ycombinator.com/library/Vz-patrick-collison-what-if-you-succeed',
  },
];

/**
 * ── Films and series ──────────────────────────────────────────────────────
 *
 * WHERE THIS CAME FROM, AND WHAT I CHANGED. The source is
 * ally-films-shortlist.md (7 Sep 2026), which was written for the RAG corpus,
 * not for founders. Its third column is addressed to Ally -- "Recommend to a
 * founder about to compromise on ethics" -- and it carries seeding directives
 * (`seed contested`, `suppress_if_distress_detected`, "catalogue, don't
 * prioritise", glossary cross-references) that mean nothing to a reader and
 * expose how the engine picks.
 *
 * So each entry is re-addressed to the founder and the directives are stripped.
 * The claim is unchanged -- only who it is spoken to. No title and no judgement
 * here was invented.
 *
 * THE WARNINGS ARE KEPT, NOT DROPPED. Part G of the source flags films that get
 * watched the wrong way round -- Wolf as aspirational, Whiplash as a model of
 * mentorship. That caution is the most founder-facing thing in the document, so
 * it renders on the card as `care` rather than being filed away internally.
 *
 * NO LINKS, DELIBERATELY. The source's copyright rule is to link nothing but an
 * official streaming listing, and those differ per title, per country and per
 * month. A rotting link is worse than no link, and a title is searchable.
 *
 * NO PLOT SUMMARIES, for the same reason: `why` says what the film is about in
 * a line, which is ours to write. Anything longer starts to substitute for
 * watching it.
 *
 * FIELDS. `why` what it is · `forWhen` when to watch it · `ask` the question
 * worth sitting with afterwards · `care` the way it is commonly misread. Only
 * `id`, `title` and `tag` are required.
 */

/** Films and documentaries. Indian first, then global, then documentary. */
export const MOVIES = [
  {
    id: 'rocket-singh',
    title: 'Rocket Singh: Salesman of the Year',
    year: '2009',
    tag: 'Indian film',
    why: 'A company built inside a company, on the premise that honesty is a sales strategy rather than a handicap.',
    forWhen: 'You are about to compromise on ethics to close a deal, you think your people are a cost line, or you are building a services business on relationships.',
    ask: 'What would your version of his non-negotiable be?',
  },
  {
    id: 'guru',
    title: 'Guru',
    year: '2007',
    tag: 'Indian film',
    why: 'Ambition, regulatory arbitrage and the moral cost of scale, loosely drawn on Dhirubhai Ambani.',
    forWhen: 'Your ambition is big and your ethics are vague.',
    care: 'It is romantic about rule-breaking in a way we would not endorse. Watch Scam 1992 alongside it.',
  },
  {
    id: 'sui-dhaaga',
    title: 'Sui Dhaaga: Made in India',
    year: '2018',
    tag: 'Indian film',
    why: 'Small-scale manufacturing, family resistance, and going from a job to your own business with no capital. Closer to the businesses GoXL actually works with than anything else on this list.',
    forWhen: 'You are first-generation and your family is sceptical.',
  },
  {
    id: 'band-baaja-baaraat',
    title: 'Band Baaja Baaraat',
    year: '2010',
    tag: 'Indian film',
    why: 'Two people start a service business with no money, succeed, then blow it up by mixing the personal and the professional.',
    forWhen: 'You have a co-founder. Watch it before the conflict, not after.',
    ask: 'What did they never write down that they should have?',
  },
  {
    id: 'manjhi',
    title: 'Manjhi: The Mountain Man',
    year: '2015',
    tag: 'Indian film',
    why: 'Twenty-two years on one obsessive project with no external validation at all.',
    forWhen: 'You are deep in a long build and have stopped believing in it.',
    care: 'Not for a founder who should actually be quitting. Endurance on its own is not a strategy.',
  },
  {
    id: 'mission-mangal',
    title: 'Mission Mangal',
    year: '2019',
    tag: 'Indian film',
    why: 'Frugal innovation under hard constraints -- doing it cheaper because there is no other option.',
    forWhen: 'You believe your problem is budget.',
  },
  {
    id: 'rocketry',
    title: 'Rocketry: The Nambi Effect',
    year: '2022',
    tag: 'Indian film',
    why: 'Deep technical work, institutional politics, and reputational destruction.',
    forWhen: 'You are technical, and navigating an institution or a public setback.',
  },
  {
    id: '12th-fail',
    title: '12th Fail',
    year: '2023',
    tag: 'Indian film',
    why: 'Repeated failure, restarting, and the psychology of trying again without a safety net.',
    forWhen: 'A venture just did not work and you are deciding whether to go again.',
    care: 'Powerful, and heavy. Not for a week when you are already low.',
  },
  {
    id: 'super-30',
    title: 'Super 30',
    year: '2019',
    tag: 'Indian film',
    why: 'Building something for a market everyone else has written off.',
    forWhen: 'You are building in education or social impact.',
  },
  {
    id: 'swades',
    title: 'Swades',
    year: '2004',
    tag: 'Indian film',
    why: 'Returning to build in India rather than outside it, and systems thinking applied at village scale.',
    forWhen: 'You are building from abroad, or building for impact.',
  },
  {
    id: 'chak-de-india',
    title: 'Chak De! India',
    year: '2007',
    tag: 'Indian film',
    why: 'Team-building out of a collection of individuals, and leadership after public disgrace.',
    forWhen: 'Your team is talented and still not a team.',
  },
  {
    id: 'lagaan',
    title: 'Lagaan',
    year: '2001',
    tag: 'Indian film',
    why: 'Assembling a team with no resources against an opponent who also sets the rules. Underdog framing without the toxicity most underdog stories carry.',
  },
  {
    id: '3-idiots',
    title: '3 Idiots',
    year: '2009',
    tag: 'Indian film',
    why: 'Curiosity over credentialism, and family expectation as a career constraint.',
    forWhen: 'Your real blocker is parental permission rather than the market.',
    ask: 'Whose permission are you still waiting for?',
  },
  {
    id: 'dangal',
    title: 'Dangal',
    year: '2016',
    tag: 'Indian film',
    why: 'Coaching, standards, and the line between pushing someone and breaking them.',
    care: 'Genuinely useful on standards and genuinely uncomfortable on autonomy. Worth arguing with rather than copying.',
  },
  {
    id: 'corporate',
    title: 'Corporate',
    year: '2006',
    tag: 'Indian film',
    why: 'Boardroom politics, competitive sabotage, and who ends up taking the fall.',
    forWhen: 'You are about to enter a partnership with a much larger company.',
  },
  {
    id: 'baazaar',
    title: 'Baazaar',
    year: '2018',
    tag: 'Indian film',
    why: 'Mentorship as extraction.',
    forWhen: 'A powerful investor or advisor is courting you.',
    ask: "What does this person want from you that you haven't priced?",
  },
  {
    id: 'the-big-bull',
    title: 'The Big Bull',
    year: '2021',
    tag: 'Indian film',
    why: 'Market manipulation and the seduction of fast money.',
    care: 'Weaker than Scam 1992, which covers the same ground better. Watch that one first.',
  },
  {
    id: 'gully-boy',
    title: 'Gully Boy',
    year: '2019',
    tag: 'Indian film',
    why: 'Building an identity and a craft against a class ceiling and family opposition.',
    forWhen: 'You are young and first-generation.',
  },
  {
    id: 'bhaag-milkha-bhaag',
    title: 'Bhaag Milkha Bhaag',
    year: '2013',
    tag: 'Indian film',
    why: 'Discipline, and performance under the weight of history.',
  },
  {
    id: 'ms-dhoni',
    title: 'M.S. Dhoni: The Untold Story',
    year: '2016',
    tag: 'Indian film',
    why: 'The long unglamorous grind before a break, and calm under pressure as a trained skill rather than a temperament.',
  },
  {
    id: 'iqbal',
    title: 'Iqbal',
    year: '2005',
    tag: 'Indian film',
    why: 'Constraint as a starting condition rather than an excuse. Short and unsentimental.',
  },

  {
    id: 'the-founder',
    title: 'The Founder',
    year: '2016',
    tag: 'Global film',
    why: "McDonald's -- systems, franchising, and how the person who builds the machine takes it from the people who built the product.",
    forWhen: 'You are confusing a great product with a great business, or about to sign a partnership without reading the terms.',
    ask: 'Who in your story is building the system?',
  },
  {
    id: 'the-social-network',
    title: 'The Social Network',
    year: '2010',
    tag: 'Global film',
    why: 'Co-founder betrayal, dilution, and the mechanics of being squeezed out of your own company.',
    forWhen: 'You are about to skip the founder agreement.',
    care: 'It dramatises contested events and glamorises one particular personality type. Drama, not record.',
  },
  {
    id: 'blackberry',
    title: 'BlackBerry',
    year: '2023',
    tag: 'Global film',
    why: 'A technical founder and a ruthless operator: scaling chaos, engineering shortcuts, and missing an inflection point.',
    forWhen: 'You are technical and resisting commercial leadership -- and just as much if you are the commercial leader.',
  },
  {
    id: 'moneyball',
    title: 'Moneyball',
    year: '2011',
    tag: 'Global film',
    why: 'Competing on evidence when you cannot compete on budget, against an establishment that dislikes it.',
    forWhen: 'You are under-resourced in a relationship-driven industry.',
    ask: 'What can you measure that they refuse to?',
  },
  {
    id: 'air',
    title: 'Air',
    year: '2023',
    tag: 'Global film',
    why: 'One negotiation, done properly. Preparation, going around the decision process, and knowing which term actually matters.',
    forWhen: 'You are about to negotiate a major deal or a raise.',
    ask: 'Which single term have you not thought about?',
  },
  {
    id: 'ford-v-ferrari',
    title: 'Ford v Ferrari',
    year: '2019',
    tag: 'Global film',
    why: "Craft versus corporate process, and the cost of being right inside an organisation that isn't.",
  },
  {
    id: 'tetris',
    title: 'Tetris',
    year: '2023',
    tag: 'Global film',
    why: 'Licensing, IP rights, and negotiating across jurisdictions and bureaucracies. Genuinely instructive on deal structure.',
  },
  {
    id: 'joy',
    title: 'Joy',
    year: '2015',
    tag: 'Global film',
    why: 'Inventing a product, then patents, manufacturing and distribution -- and being financially outmanoeuvred by family and partners.',
    forWhen: 'You are a woman founder, or running a family business.',
  },
  {
    id: 'the-big-short',
    title: 'The Big Short',
    year: '2015',
    tag: 'Global film',
    why: 'Holding a contrarian position while everyone calls you wrong, and the cost of being early.',
  },
  {
    id: 'margin-call',
    title: 'Margin Call',
    year: '2011',
    tag: 'Global film',
    why: 'Decision-making in the first hours of a crisis, at every level of a hierarchy. Calm rather than lurid.',
    forWhen: 'You are in an actual crisis this week.',
    ask: 'What is the first irreversible decision in front of you?',
  },
  {
    id: 'glengarry-glen-ross',
    title: 'Glengarry Glen Ross',
    year: '1992',
    tag: 'Global film',
    why: 'What a sales culture becomes under pure pressure with no support.',
    forWhen: 'You are about to install an aggressive incentive scheme.',
    care: 'Strong language throughout.',
  },
  {
    id: 'pursuit-of-happyness',
    title: 'The Pursuit of Happyness',
    year: '2006',
    tag: 'Global film',
    why: 'Persistence under genuine financial precarity.',
    care: 'Widely loved, and it quietly teaches that endurance alone is a strategy. It is not.',
  },
  {
    id: 'chef',
    title: 'Chef',
    year: '2014',
    tag: 'Global film',
    why: 'Leaving a stable job to run a small business, and finding customers through social media. Charming, low-stakes, and closer to most small-business reality than any unicorn story.',
  },
  {
    id: 'apollo-13',
    title: 'Apollo 13',
    year: '1995',
    tag: 'Global film',
    why: 'Structured problem-solving under a hard constraint and a hard deadline.',
  },
  {
    id: 'hidden-figures',
    title: 'Hidden Figures',
    year: '2016',
    tag: 'Global film',
    why: "Delivering under institutional resistance, and making your contribution legible when the system won't do it for you.",
  },
  {
    id: 'the-intern',
    title: 'The Intern',
    year: '2015',
    tag: 'Global film',
    why: 'A founder who cannot delegate, scaling faster than her own management capability. Lands the delegation point better than most business books.',
    forWhen: 'You are the bottleneck and you know it.',
    ask: 'What are you holding that someone else could hold badly for six months?',
  },
  {
    id: 'whiplash',
    title: 'Whiplash',
    year: '2014',
    tag: 'Global film',
    why: 'Brilliant on the pursuit of mastery.',
    care: 'Actively dangerous as a model of mentorship. Only worth watching with the counter-question attached: did the method work, or did he survive it?',
  },
  {
    id: 'wolf-of-wall-street',
    title: 'The Wolf of Wall Street',
    year: '2013',
    tag: 'Global film',
    why: 'A cautionary case, and only that.',
    care: 'Routinely watched as aspirational, which is the exact opposite of the intended reading.',
  },
  {
    id: 'barbarians-at-the-gate',
    title: 'Barbarians at the Gate',
    year: '1993',
    tag: 'Global film',
    why: 'Leveraged buyouts, ego, and what happens to a company once it becomes a financial asset.',
    forWhen: 'You are considering private-equity money.',
  },

  {
    id: 'startup-com',
    title: 'Startup.com',
    year: '2001',
    tag: 'Documentary',
    why: 'Two childhood friends build a company and lose the friendship. Filmed as it happened, not reconstructed -- the most honest film about co-founder breakdown there is.',
    forWhen: 'Before the partnership, not after.',
    ask: 'What did they never write down?',
  },
  {
    id: 'general-magic',
    title: 'General Magic',
    year: '2018',
    tag: 'Documentary',
    why: 'A company that was right about everything and a decade too early, whose alumni went on to build the iPhone and eBay. The best treatment there is of timing as its own distinct failure mode.',
    forWhen: "Your product is good and your market isn't ready.",
    ask: 'Are you early, or are you wrong? What evidence would tell you which?',
  },
  {
    id: 'the-inventor',
    title: 'The Inventor: Out for Blood in Silicon Valley',
    year: '2019',
    tag: 'Documentary',
    why: 'Theranos, in documentary form.',
    care: 'The Dropout covers the same ground as drama. One of the two is enough.',
  },
  {
    id: 'fyre',
    title: 'Fyre',
    year: '2019',
    tag: 'Documentary',
    why: 'Selling something that does not exist, and the moment marketing outruns operations.',
    forWhen: 'You are over-promising on delivery capacity.',
    ask: 'What happens the week after they say yes?',
  },
  {
    id: 'enron',
    title: 'Enron: The Smartest Guys in the Room',
    year: '2005',
    tag: 'Documentary',
    why: 'Culture and incentives producing fraud without anyone ever deciding to commit fraud.',
  },
  {
    id: 'something-ventured',
    title: 'Something Ventured',
    year: '2011',
    tag: 'Documentary',
    why: 'How venture capital actually started, told by the people who did it.',
    forWhen: 'Grounding, before you raise.',
  },
  {
    id: 'american-factory',
    title: 'American Factory',
    year: '2019',
    tag: 'Documentary',
    why: 'Cross-cultural manufacturing, labour, and two incompatible definitions of a good workplace.',
    forWhen: 'You manufacture in India with foreign partners or customers.',
  },
  {
    id: 'print-the-legend',
    title: 'Print the Legend',
    year: '2014',
    tag: 'Documentary',
    why: 'Two 3D-printing startups, same market, opposite outcomes. Good on hardware, funding pressure and founder replacement.',
  },
  {
    id: 'jiro-dreams-of-sushi',
    title: 'Jiro Dreams of Sushi',
    year: '2011',
    tag: 'Documentary',
    why: 'Mastery, craft, and the decision to stay small and be the best. The best counterweight there is to scale-as-the-only-goal.',
    forWhen: 'You are deciding whether to scale at all.',
    ask: 'What does the best possible small version of this look like?',
  },
  {
    id: 'free-solo',
    title: 'Free Solo',
    year: '2018',
    tag: 'Documentary',
    why: 'Preparation as the thing that makes risk survivable.',
  },
  {
    id: 'becoming-warren-buffett',
    title: 'Becoming Warren Buffett',
    year: '2017',
    tag: 'Documentary',
    why: 'Temperament, patience and compounding. A calm antidote to hustle content.',
  },
  {
    id: 'inside-job',
    title: 'Inside Job',
    year: '2010',
    tag: 'Documentary',
    why: 'Systemic incentive failure, traced end to end.',
    forWhen: 'You are building in fintech or regulated finance.',
  },
];

/** Multi-part shows. Indian first, then global. */
export const SERIES = [
  {
    id: 'tvf-pitchers',
    title: 'TVF Pitchers',
    year: '2015',
    tag: 'Indian series',
    why: 'Four people quit their jobs to start up: funding, co-founder friction, family pressure, and the gap between the pitch and the reality. The most relevant Indian screen content there is for early founders. Season 2 is weaker but covers scaling and investor dynamics.',
    forWhen: 'You are at the very beginning -- idea to first build.',
  },
  {
    id: 'scam-1992',
    title: 'Scam 1992: The Harshad Mehta Story',
    year: '2020',
    tag: 'Indian series',
    why: 'The best-made Indian business drama there is. Financial-system exploitation, the ratchet from grey to illegal, and how a system quietly enables it.',
    forWhen: 'You are rationalising a shortcut.',
    ask: 'Where exactly was the line, and had he already crossed it by then?',
  },
  {
    id: 'rocket-boys',
    title: 'Rocket Boys',
    year: '2022',
    tag: 'Indian series',
    why: 'Institution-building, scientific ambition, and long-horizon work under political constraint.',
    forWhen: 'You are building deep tech or hardware.',
  },
  {
    id: 'shark-tank-india',
    title: 'Shark Tank India',
    year: '2021–',
    tag: 'Indian series',
    why: 'Useful as a prompt rather than as a model. Pick one episode and find the question you would have failed on.',
    care: 'It badly distorts what fundraising actually is — it compresses valuation into theatre, and has left a lot of founders believing a pitch is a business.',
  },
  {
    id: 'panchayat',
    title: 'Panchayat',
    year: '2020–',
    tag: 'Indian series',
    why: 'Not a business show, but the best portrayal available of operating inside Indian bureaucratic and community reality.',
    forWhen: 'Your go-to-market depends on government, rural distribution or local trust.',
  },

  {
    id: 'silicon-valley',
    title: 'Silicon Valley',
    year: '2014–19',
    tag: 'Global series',
    why: 'Comedy, and the most accurate thing ever made about startup life -- cap tables, pivots, board coups, term sheets.',
    forWhen: 'You need to laugh and learn at the same time.',
  },
  {
    id: 'the-dropout',
    title: 'The Dropout',
    year: '2022',
    tag: 'Global series',
    why: 'Theranos. Narrative outrunning evidence, and the machinery that lets it happen. The essential counterweight to founder-conviction mythology.',
  },
  {
    id: 'wecrashed',
    title: 'WeCrashed',
    year: '2022',
    tag: 'Global series',
    why: 'WeWork. Capital as an accelerant for delusion, and governance failure at scale.',
  },
  {
    id: 'super-pumped',
    title: 'Super Pumped: The Battle for Uber',
    year: '2022',
    tag: 'Global series',
    why: "Growth culture as a failure mode -- the point where 'aggressive' becomes the company's actual product.",
  },
  {
    id: 'the-playlist',
    title: 'The Playlist',
    year: '2022',
    tag: 'Global series',
    why: 'Spotify, told from six conflicting perspectives. The format is the lesson: every founding story is contested, and everyone believes they were the reason.',
    forWhen: 'You and your co-founder remember it differently.',
    ask: 'Whose version of the story are you telling?',
  },
  {
    id: 'halt-and-catch-fire',
    title: 'Halt and Catch Fire',
    year: '2014–17',
    tag: 'Global series',
    why: 'The best long-form portrait of repeated failure, reinvention, and what a decade of building does to people. Slow start, worth it.',
    care: 'Emotionally heavy on failure.',
  },
  {
    id: 'mad-men',
    title: 'Mad Men',
    year: '2007–15',
    tag: 'Global series',
    why: 'Positioning, pitching, and the psychology of what people actually buy.',
    care: 'Worth specific episodes rather than the whole run.',
  },
  {
    id: 'the-last-dance',
    title: 'The Last Dance',
    year: '2020',
    tag: 'Global series',
    why: 'Standards, and the human cost of enforcing them.',
  },
];

/* Said once at the top of a list rather than as a caveat on sixty-five cards.
   It is the single most important thing to know about a collection like this,
   and repeating it would turn it into wallpaper. */
const SURVIVORSHIP =
  'Almost every story here is about someone who made it — the ones who did not rarely get filmed. Read them with that in mind.';

/**
 * The tabs, in the order they appear. `slug` is what the URL carries, so a
 * founder can be sent straight to one.
 *
 * `variant` picks the card. Podcasts are links, so they render as link cards.
 * Films and series have no link worth giving, so they render as title tiles
 * that open their detail on hover, on focus, or on tap.
 */
export const WATCH_TABS = [
  {
    slug: 'podcasts',
    label: 'Podcasts',
    variant: 'links',
    items: PODCASTS,
    empty: 'Nothing here yet.',
  },
  {
    slug: 'series',
    label: 'Series',
    variant: 'titles',
    items: SERIES,
    standing: SURVIVORSHIP,
    empty: 'Nothing here yet. Series take a while to vet — a good one is several hours of somebody’s attention.',
  },
  {
    slug: 'movies',
    label: 'Movies',
    variant: 'titles',
    items: MOVIES,
    standing: SURVIVORSHIP,
    empty: 'Nothing here yet. We would rather list two films worth an evening than twenty that are not.',
  },
];
