import { WATCH_TABS } from './watch';

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

/** Long-form: books, essays, papers, posts. */
export const THINGS_TO_READ = [];

/* "Things to watch" is the one section with sub-tabs, because podcasts, series
   and films are three different sizes of commitment and mixing them makes the
   list unreadable. Its content lives in data/watch.js. */

/** Courses and structured programmes -- things with a beginning and an end. */
export const THINGS_TO_LEARN = [];

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
    sub: 'Books, essays and posts the team has actually read and would hand to a founder.',
    empty: 'Nothing here yet. We are only listing things we have read ourselves, so this fills up slowly and on purpose.',
    items: THINGS_TO_READ,
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
    title: 'Worth the effort.',
    sub: 'Courses and programmes for when a gap needs more than an afternoon.',
    empty: 'Nothing here yet. These take longer to vet than a link, so they arrive one at a time.',
    items: THINGS_TO_LEARN,
  },
};
