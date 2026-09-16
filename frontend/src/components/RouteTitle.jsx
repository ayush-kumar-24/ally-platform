import { useEffect } from 'react';
import { useLocation } from 'react-router-dom';

/**
 * Keeps <title> in step with the route.
 *
 * Every route rendered the same "Ally — Founder DNA Platform · GoXL" that
 * index.html ships with, so browser history, bookmarks, open tabs and screen
 * readers (which announce the title on navigation) all described fourteen
 * different screens identically. Renders nothing.
 */

const SUFFIX = 'Ally · GoXL';

/* Exported because PlatformLayout's topbar needs a name for routes that are
   not nav items -- Plans & billing, Know my energy, Clarity report. It kept
   its own list, which simply had no entry for those, so each of them printed
   the fallback label as its heading. */
export const TITLES = {
  '/': 'Ally — Founder DNA Platform · GoXL',
  '/terms': 'Terms of Service',
  '/privacy': 'Privacy Policy',

  /* Bare /guided has no page of its own -- it redirects to login. Named so
     the title does not flash "Page not found" during the redirect frame. */
  '/guided': 'Sign in',
  '/guided/login': 'Sign in',
  '/guided/resume': 'Pick up where you left off',
  '/guided/expectation': 'How it works',
  '/guided/welcome': 'Welcome',
  '/guided/ally-intro': 'Meet Ally',
  '/guided/profile': 'Building your profile',
  '/guided/tour': 'First impression',
  '/guided/summary': 'Your founder summary',
  '/guided/validate': 'A quick check',
  '/guided/problem': 'The perceived problem',

  '/app': 'Compass',
  '/app/ally-chat': 'Talk to Ally',
  '/app/founder-dna-journey': 'Mapping your Founder DNA',
  '/app/current-problem': 'The problem as you see it',
  '/app/diagnosis': 'Your diagnosis',
  '/app/thinking': 'Ally is thinking',
  '/app/founder-dna': 'Founder DNA',
  '/app/vision': 'Your Vision',
  '/app/business-dna': 'Business DNA',
  '/app/journey': 'Journey',
  '/app/achievements': 'Your Achievements',
  '/app/goals': 'Goals',
  '/app/recommendations': 'Recommendations',
  '/app/frameworks': 'Frameworks',
  /* One component, section chosen by the :section param -- but spelled out
     literally rather than matched by prefix, because those three are the only
     real sections. /app/knowledge/anything-else renders KnowledgePage's own
     "that section does not exist", so it SHOULD get the not-found title. */
  '/app/knowledge/read': 'Things to read',
  '/app/knowledge/watch': 'Things to watch',
  '/app/knowledge/learn': 'Things to learn',
  '/app/profile': 'Your profile',
  '/app/plan': 'Plan your day',
  '/app/know-my-energy': 'Know my energy',
  '/app/next-steps': 'Next steps',
  '/app/discovery-call': 'Discovery call',
  '/app/feedback': 'Send feedback',
  '/app/report': 'Clarity report',
  '/app/billing': 'Plans & billing',
  '/app/help': 'Help & support',

  '/admin': 'Admin · Dashboard',
  '/admin/users': 'Admin · Users',
  '/admin/usage': 'Admin · Usage',
  '/admin/calls': 'Admin · Calls',
  '/admin/waitlist': 'Admin · Waitlist',
  '/admin/privacy': 'Admin · Privacy',
  '/admin/feedback': 'Admin · Feedback',
  '/admin/audit': 'Admin · Audit log',
  '/admin/coupons': 'Admin · Coupons',
  '/admin/launch': 'Admin · Launch',
  '/admin/system': 'Admin · System',
};

/* Routes with a param in them, which cannot be literals above.

   Kept deliberately short. Every route that CAN be a literal is one, because a
   literal is the accurate title; a pattern can only give the generic name of
   the kind of page. A framework's own name would need the frameworks data
   imported here, and this component renders on every route -- that would pull
   the whole catalogue into the initial bundle to set a string. */
const PATTERNS = [
  [/^\/app\/frameworks\/[^/]+$/, 'Framework'],
  [/^\/admin\/users\/[^/]+$/, 'Admin · User detail'],
];

/* A trailing slash is the same route. /app/plan/ and /app/plan are one page,
   and only one of them used to get a title. */
const normalise = (pathname) => pathname.replace(/\/+$/, '') || '/';

function titleForPath(pathname) {
  const path = normalise(pathname);

  const exact = TITLES[path];
  if (exact) return exact === TITLES['/'] ? exact : `${exact} · ${SUFFIX}`;

  const pattern = PATTERNS.find(([re]) => re.test(path));
  if (pattern) return `${pattern[1]} · ${SUFFIX}`;

  /* ONLY REAL 404s REACH HERE. This used to be the fallback for any route
     missing from the map as well, which is how "Things to read" -- a page that
     renders perfectly -- announced itself to the tab strip, to bookmarks and
     to a screen reader as "Page not found". A route that exists and is absent
     from the map above is a bug in the map, not a missing page. */
  return `Page not found · ${SUFFIX}`;
}

export default function RouteTitle() {
  const { pathname } = useLocation();

  useEffect(() => {
    document.title = titleForPath(pathname);
  }, [pathname]);

  return null;
}
