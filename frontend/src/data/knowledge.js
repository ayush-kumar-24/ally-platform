import { WATCH_TABS } from './watch';
import { READ_TABS } from './read';
import { GLOSSARY, GLOSSARY_TERM_COUNT } from './glossary';

/**
 * data/knowledge.js — the three reference libraries under KNOWLEDGE.
 *
 * Same category as data/frameworks.js: static reference material, not a claim
 * about the signed-in founder. Nothing here is personalised, and nothing here
 * is generated — a founder sees exactly what the team put in.
 *
 * DELIBERATELY EMPTY UNTIL THE TEAM FILLS IT. Seeding these with plausible
 * book titles and video links would put recommendations in front of founders
 * that nobody at GoXL actually chose, on a page whose entire value is that
 * somebody did choose them. The pages render an honest empty state instead.
 *
 * TO ADD AN ITEM, push an object onto the right array. Every field is optional
 * except `id` and `title`, so a half-known entry is still publishable:
 *
 *   {
 *     id: 'lean-startup',          // unique within its section, used as a key
 *     title: 'The Lean Startup',
 *     by: 'Eric Ries',             // author, channel, or provider
 *     length: '9 hours',           // reading/watch/course time, in words
 *     why: 'Why a founder should spend time on this, in one sentence.',
 *     forWhen: 'You are about to build something nobody asked for.',
 *     url: 'https://...',          // opens in a new tab; omit for offline items
 *   }
 */

/* "Things to read" is tabbed by theme -- see data/read.js. A founder looking
   for help with pricing should not have to scroll past a hundred books about
   something else. */

/* "Things to watch" is the one section with sub-tabs, because podcasts, series
   and films are three different sizes of commitment and mixing them makes the
   list unreadable. Its content lives in data/watch.js. */

/* "Things to learn" is a glossary rather than a list of courses -- a searchable
   reference, not something you click out to. See data/glossary.js. */

/**
 * One place that describes all three sections, so the nav, the routes and the
 * pages cannot drift apart. The page component reads this rather than hard
 * coding a heading per file.
 */
export const KNOWLEDGE_SECTIONS = {
  read: {
    slug: 'read',
    kicker: 'Things to read',
    title: 'Worth the hours.',
    sub: 'Books worth the hours, grouped by what you need them for. Tap one to look it up.',
    empty: 'Nothing here yet. We are only listing things we have read ourselves, so this fills up slowly and on purpose.',
    tabs: READ_TABS,
  },
  watch: {
    slug: 'watch',
    kicker: 'Things to watch',
    title: 'Worth the time.',
    sub: 'Talks and conversations that say something a blog post could not.',
    empty: 'Nothing here yet. We would rather show you three things worth watching than thirty we have not.',
    /* Tabbed rather than one list -- see WATCH_TABS. `items` is unused for this
       section and deliberately absent, so a reader does not wonder which of the
       two the page renders. */
    tabs: WATCH_TABS,
  },
  learn: {
    slug: 'learn',
    kicker: 'Things to learn',
    title: 'Worth knowing.',
    sub: `${GLOSSARY_TERM_COUNT} terms an early founder is expected to know and usually is not told. Search it, or read a section.`,
    empty: 'Nothing here yet.',
    variant: 'glossary',
    glossary: GLOSSARY,
  },
};
