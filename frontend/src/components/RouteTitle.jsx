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

const TITLES = {
  '/': 'Ally — Founder DNA Platform · GoXL',
  '/terms': 'Terms of Service',
  '/privacy': 'Privacy Policy',

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

  '/app': 'Dashboard',
  '/app/ally-chat': 'Chat with Ally',
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
  '/admin/audit': 'Admin · Audit log',
  '/admin/system': 'Admin · System',
};

function titleForPath(pathname) {
  const exact = TITLES[pathname];
  if (exact) return exact === TITLES['/'] ? exact : `${exact} · ${SUFFIX}`;
  // /admin/users/:id and anything else that didn't match a literal above.
  if (pathname.startsWith('/admin/users/')) return `Admin · User detail · ${SUFFIX}`;
  return `Page not found · ${SUFFIX}`;
}

export default function RouteTitle() {
  const { pathname } = useLocation();

  useEffect(() => {
    document.title = titleForPath(pathname);
  }, [pathname]);

  return null;
}
