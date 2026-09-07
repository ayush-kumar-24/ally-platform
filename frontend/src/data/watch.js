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

/** Multi-part shows worth following. Nothing chosen yet. */
export const SERIES = [];

/** Films and documentaries. Nothing chosen yet. */
export const MOVIES = [];

/**
 * The tabs, in the order they appear. `slug` is what the URL carries, so a
 * founder can be sent straight to one.
 */
export const WATCH_TABS = [
  {
    slug: 'podcasts',
    label: 'Podcasts',
    items: PODCASTS,
    empty: 'Nothing here yet.',
  },
  {
    slug: 'series',
    label: 'Series',
    items: SERIES,
    empty: 'Nothing here yet. Series take a while to vet — a good one is several hours of somebody’s attention.',
  },
  {
    slug: 'movies',
    label: 'Movies',
    items: MOVIES,
    empty: 'Nothing here yet. We would rather list two films worth an evening than twenty that are not.',
  },
];
