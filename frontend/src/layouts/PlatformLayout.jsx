import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import DeletionPendingGate from '../components/DeletionPendingGate';
import ReconsentGate from '../components/ReconsentGate';
import PlanRequiredGate from '../components/PlanRequiredGate';
import HelpWidget from '../components/HelpWidget';
import { useApp } from '../context/AppContext';
import { checkProfileComplete } from '../services/onboarding';
import { planLabel as planLabelFor } from '../services/plans';
import { usePlanName, usePlanTier } from '../hooks/usePlanName';
import { useState, useRef, useEffect } from 'react';
import ProductTour from '../components/ProductTour';
import { TITLES as ROUTE_TITLES } from '../components/RouteTitle';
import { greetingNow } from '../utils/helpers';
import { getOverview } from '../services/dashboard';
import { loadVision } from '../services/vision';
import { firstSafe } from '../utils/looksLikeToken';
import {
  IconDashboard,
  IconCreditCard,
  IconMessageSquare,
  IconUser,
  IconTrendingUp,
  IconDocument,
  IconLock,
  IconArrowRight,
  IconCalendar,
  IconHelpCircle,
  IconPlay,
  IconSettings,
  IconBell,
  IconEye,
  IconMapPin,
  IconAward,
  IconList,
  IconLightbulb,
  IconBook,
  IconFile,
  IconTarget,
} from '../utils/icons';

function IconPulse(props) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" width="1em" height="1em" {...props}>
      <circle cx="12" cy="12" r="3" />
      <path d="M12 2v3m0 14v3M2 12h3m14 0h3m-3.5-7.5-2.1 2.1M7.6 16.4l-2.1 2.1m0-12.9 2.1 2.1m8.7 8.7 2.1 2.1" />
    </svg>
  );
}

const ROUTE_EYE = {
  '/app': 'Overview',
  '/app/ally-chat': 'Conversation',
  '/app/founder-dna-journey': 'Founder first',
  '/app/current-problem': 'In your words',
  /* "Business DNA", not "Diagnosis", because that is what these questions are
     building: the diagnosis IS the Business DNA assessment -- six pillars and
     twenty dimensions (api/v1/diagnosis/business_dna.py). The founder has just
     come off a Founder DNA interview headed "Founder first" and this panel
     said nothing to place the second half, so there was no way to tell from
     the screen that the business was now the subject.

     The '/app/business-dna' route below reads 'Business' for the same reason
     in reverse: it is where the finished DNA is READ, not built. */
  '/app/diagnosis': 'Business DNA',
  '/app/founder-dna': 'Founder first',
  '/app/vision': 'Long-term',
  '/app/business-dna': 'Business',
  '/app/journey': 'Momentum',
  '/app/achievements': 'Milestones',
  '/app/goals': 'Outcomes',
  '/app/recommendations': 'What to do next',
  '/app/frameworks': 'Thinking toolkit',
  /* A category, not a second name for the page. It used to read "Executive
     report", which put a third name on a screen that already called itself two
     things. The other entries in this map are categories -- Overview,
     Conversation, Long-term -- and this one now is too. */
  '/app/report': 'Your diagnosis',
  '/app/next-steps': 'Momentum',
  '/app/plan': 'Today',
  '/app/discovery-call': 'Talk to a human',
  '/app/feedback': 'Tell us what you think',
  '/app/profile': 'Founder identity',
  '/app/help': "We're here to help",
};

/* The vision item names what the founder has, not what the route is: an
   invitation until the first territory is written, a possession after. null is
   "not loaded yet" and keeps the neutral wording. Used for the sidebar label
   and the page's own title, so the two can never disagree. */
function visionLabel(hasVision) {
  if (hasVision === null) return 'Your Vision';
  return hasVision ? 'Your Vision Board' : 'Build Your Vision';
}

const NAV_GROUPS = [
  {
    label: 'HOME',
    items: [
      { path: '/app', tip: 'Compass', icon: IconDashboard, label: 'Compass', badge: null },
      { path: '/app/ally-chat', tip: 'Talk to Ally', icon: IconMessageSquare, label: 'Talk to Ally', badge: null },
    ],
  },
  {
    /* No heading over this group. It had one -- FOUNDER DIAGNOSIS -- but it
       covers everything from the diagnosis to Plan Your Day and a discovery
       call, so the words described the first two items and mislabelled the
       rest. `label` is still the React key and is still what the collapsed
       rail groups by; only the visible heading is gone. */
    label: 'FOUNDER DIAGNOSIS',
    hideLabel: true,
    items: [
      /* Entry point first, then the pages it produces. "Adaptive diagnosis" is
         the thing a founder runs; Founder DNA and Business DNA are written
         *from* it and stay locked until there is a report.

         This reverses the 2026-08-27 order, which put the two result pages
         first so the section read as the journey. It read instead as two
         locked rows above the one row a new founder could actually click --
         the map was there, but the door was below it. (2026-09-05 product
         decision.) */
      /* needsProfile: the API refuses /founder-dna/start, /current-problem/start
         and /diagnosis/start until onboarding is finished. Showing this row as
         open would be advertising a door that answers 409. */
      { path: '/app/founder-dna-journey', tip: 'Adaptive diagnosis', icon: IconPulse, label: 'Adaptive diagnosis', badge: null, needsProfile: true },
      { path: '/app/founder-dna', tip: 'Founder DNA', icon: IconUser, label: 'Founder DNA', badge: null, needsReport: true },
      { path: '/app/business-dna', tip: 'Business DNA', icon: IconTrendingUp, label: 'Business DNA', badge: null, needsReport: true },
      /* Unlike the DNA pages above, this isn't derived from a diagnosis report
         -- it's the founder's own long-term vision, written whenever they like.
         No needsReport gate: nothing here depends on one existing. */
      { path: '/app/vision', tip: 'Your Vision', icon: IconEye, label: 'Your Vision', badge: null },
      /* Not built yet -- comingSoon shows the same lock treatment as a
         needsReport item but opens its own honest "coming soon" page
         instead of redirecting into the diagnosis flow. */
      { path: '/app/journey', tip: 'Journey', icon: IconMapPin, label: 'Journey', badge: null, comingSoon: true },
      /* Not gated on report/plan -- gated on actually having talked to Ally
         enough for there to be anything to remember. See
         services/achievements.js: the page itself checks real message
         counts and shows its own unlock progress; the nav lock here is
         just the same visual treatment with a matching tooltip. */
      { path: '/app/achievements', tip: 'Your Achievements', icon: IconAward, label: 'Your Achievements', badge: null, comingSoon: true, lockTip: 'Talk to Ally to unlock' },
      /* Unlike Achievements, nothing here depends on Ally having learned
         anything -- a founder can set a goal the moment they land here. No
         lock. */
      { path: '/app/goals', tip: 'Goals', icon: IconList, label: 'Goals', badge: null },
      /* Real diagnosis output, same as Founder DNA/Business DNA/Report above --
         gated the same way, not founder-authored like Vision/Goals. */
      { path: '/app/recommendations', tip: 'Recommendations', icon: IconLightbulb, label: 'Recommendations', badge: null, needsReport: true },
      { path: '/app/report', tip: 'Report', icon: IconDocument, label: 'Report', badge: null, needsReport: true },
      { path: '/app/next-steps', tip: 'Next steps', icon: IconArrowRight, label: 'Next steps', badge: null, needsReport: true },
      /* badge was hardcoded to 3 — every founder saw "3 tasks due" forever,
         including one who had never opened the planner. Null until it can be
         driven by a real due-task count. */
      { path: '/app/plan', tip: 'Plan Your Day', icon: IconCalendar, label: 'Plan Your Day', badge: null },
      /* comingSoon, not a plan lock. Booking is built but cannot be hosted
         until Workspace domain verification lands, and no plan unlocks it
         early -- so the tooltip says when, not what to buy.

         Still navigable on purpose: comingSoon shows the padlock without
         setting aria-disabled or intercepting the click, so the row opens the
         page's own coming-soon banner rather than dead-ending. */
      { path: '/app/discovery-call', tip: 'Book a discovery call', icon: IconCalendar, label: 'Discovery call', badge: null, comingSoon: true, lockTip: 'Opening in a few days' },
    ],
  },
  {
    /* Knowledge is the major heading; Frameworks is one part of it. Moved out
       of FOUNDER DIAGNOSIS because it never belonged there: everything else
       under that heading is either a diagnosis step or written from a
       diagnosis, while this is static reference content (data/frameworks.js)
       available from the moment a founder lands. Its own section leaves room
       for the other reference material to join it under one heading rather
       than accumulating at the bottom of a list about something else. */
    label: 'KNOWLEDGE',
    items: [
      { path: '/app/frameworks', tip: 'Frameworks', icon: IconBook, label: 'Frameworks', badge: null },
      /* The three reference libraries the section was left room for. Ordered by
         how much of a founder's time each one asks for -- an article, then a
         talk, then a course -- so the cheapest thing to act on is nearest the
         top. Distinct icons on purpose: three book-ish glyphs in one group
         reads as one repeated item rather than three choices. */
      { path: '/app/knowledge/read', tip: 'Things to read', icon: IconFile, label: 'Things to read', badge: null },
      { path: '/app/knowledge/watch', tip: 'Things to watch', icon: IconPlay, label: 'Things to watch', badge: null },
      { path: '/app/knowledge/learn', tip: 'Things to learn', icon: IconTarget, label: 'Things to learn', badge: null },
    ],
  },
  {
    /* Its own group rather than tacked onto the end of FOUNDER DIAGNOSIS --
       feedback is not a diagnosis step, and burying it under that heading is
       how a suggestion box goes unread. */
    label: 'YOUR FEEDBACK',
    items: [
      { path: '/app/feedback', tip: 'Send feedback', icon: IconMessageSquare, label: 'Send feedback', badge: null },
    ],
  },
  {
    label: 'ACCOUNT',
    items: [
      { path: '/app/profile', tip: 'Profile', icon: IconSettings, label: 'Profile', badge: null },
      /* Plan management belongs with the other account rows. It used to be a
         card of its own pinned above the founder's name -- the heaviest object
         in the sidebar, sitting in the spot the eye lands on last, saying
         exactly what the header pill already says and going exactly where the
         header pill already goes. planBadge asks for the live "Upgrade" chip,
         since NAV_GROUPS is a module constant and cannot read the tier. */
      { path: '/app/billing', tip: 'Plan & billing', icon: IconCreditCard, label: 'Plan & billing', badge: null, planBadge: true },
      /* Not a page -- it starts the tour where the founder already is. The tour
         spotlights the sidebar itself, so sending them somewhere first would
         move the very thing it is about to point at. `action` is what marks an
         item as doing something rather than going somewhere. */
      { action: 'tour', tip: 'Replay the product tour', icon: IconPlay, label: 'Product tour', badge: null },
      { path: '/app/help', tip: 'Help & Support', icon: IconHelpCircle, label: 'Help & Support', badge: null },
    ],
  },
];

export default function PlatformLayout() {
  const { user, sidebarCollapsed, toggleSidebar, sidebarOpen, openSidebar, closeSidebar,
          notifications, clearNotifications, markAllNotificationsRead,
          unreadCount, readNotification,
          hasVision, setHasVision, startTour } = useApp();

  /* Both of these read "Ally Free" as literal text, so a paying founder was
     shown the free badge everywhere. `user.plan` is hydrated from the server
     profile -- but it is a TIER ID, not a plan name, and the label used to be
     built out of it: the map here had no `basic` entry, so a founder who had
     just paid Rs 199 for the plan everything else calls "Starter" was shown
     "Ally Basic" and reasonably concluded the payment had not applied. Worse,
     it mapped `starter` to "Ally Starter" as well, so the Rs 499 plan and the
     Rs 199 plan rendered identically. planLabel() reads the catalog's own
     name, from the server where it has arrived. */
  const serverPlanName = usePlanName();
  const serverTier = usePlanTier();
  /* The server's tier wins over the profile's. `user.plan` is hydrated at
     sign-in and never refreshed when a plan changes, so a founder who had just
     upgraded was still offered "Upgrade plan" -- on the very page that had
     taken their money. The profile stays as the fallback for the moment before
     GET /plans/me answers, which is what keeps the button from flickering. */
  const planTier = (serverTier || user?.plan || 'free').toLowerCase();
  const planLabel = planLabelFor(planTier, serverPlanName);
  const onTopTier = planTier === 'pro';
  const nav = useNavigate();
  const location = useLocation();
  const [npOpen, setNpOpen] = useState(false);
  const npRef = useRef(null);

  /* Whether onboarding is finished. Starts true for the same reason
     hasReport does -- a slow call must not lock anyone out. */
  const [profileComplete, setProfileComplete] = useState(true);
  /* Whether a diagnosis has actually produced a report yet -- what decides
     which nav items are still locked. Starts unlocked so a slow call never
     shuts a founder out of pages they have already earned. */
  const [hasReport, setHasReport] = useState(true);
  // Independent of AppContext's user.name -- live-confirmed a real gap: right
  // after a fresh login, this header could render "there" for several
  // seconds (or longer) while Dashboard.jsx's OWN greeting, fetched from this
  // exact same endpoint, already showed the real name correctly. Whatever
  // causes AppContext's hydration to lag (timing between the login flow's
  // setUser and this component's mount, or a missed re-run), this component
  // sees every route change (it's the persistent chrome, not the routed
  // page), so it does not need to depend on that context value alone.
  const [founderName, setFounderName] = useState(null);
  useEffect(() => {
    let cancelled = false;
    getOverview()
      .then(o => {
        if (cancelled || !o) return;
        setHasReport(Boolean(o.latest_diagnosis?.available));
        if (o.founder_name) setFounderName(o.founder_name);
      })
      .catch(() => { /* leave unlocked rather than guess */ });

    /* Same fail-open rule as hasReport above: if the check cannot be reached we
       leave the row open and let the server say no, rather than locking a
       founder out of a diagnosis they are entitled to. */
    checkProfileComplete()
      .then((r) => { if (!cancelled) setProfileComplete(r?.valid !== false); })
      .catch(() => { /* leave unlocked rather than guess */ });
    /* One request per session for one word in the sidebar. It rides in the
       effect that already runs here rather than in AppContext, because this
       component is inside the auth gate and the provider is not -- fetching
       there would fire before there is a session to fetch with. A failure
       leaves hasVision null, which is the neutral label, not a wrong one. */
    loadVision()
      .then(v => {
        if (cancelled) return;
        setHasVision(Object.values(v.territories).some(t => t.statement.trim()));
      })
      .catch(() => { /* neutral label */ });
    return () => { cancelled = true; };
  }, []);

  const handleNav = (path) => {
    nav(path);
    closeSidebar();
  };

  useEffect(() => {
    const handler = (e) => {
      if (npRef.current && !npRef.current.contains(e.target)) setNpOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  /* The mobile drawer could be opened from the keyboard (the burger is a real
     button) but only dismissed by pointing at the scrim -- so a keyboard user
     could open it and had no way back out except tabbing through the whole
     drawer. Escape is what every other overlay in the app already honours. */
  useEffect(() => {
    if (!sidebarOpen) return undefined;
    const onKey = (e) => { if (e.key === 'Escape') closeSidebar(); };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [sidebarOpen, closeSidebar]);

  const isActive = (path) => {
    if (path === '/app') return location.pathname === '/app' || location.pathname === '/app/';
    return location.pathname.startsWith(path);
  };

  /* Nav label first, then the route-title map, and only then a fallback.
     The map is the reason: several real routes -- Plans & billing, Know my
     energy, Clarity report -- are not nav items at all, so the nav lookup
     misses and every one of them used to print the fallback as its heading.
     That was already wrong when the fallback read "Dashboard"; renaming it
     made the billing page announce itself as "Compass", which is how it got
     noticed. ROUTE_TITLES already names every route, so it is the answer
     rather than a second copy of it kept in sync by hand. */
  const currentLabel =
    NAV_GROUPS.flatMap(g => g.items).find(i => isActive(i.path))?.label
    || ROUTE_TITLES[location.pathname.replace(/\/$/, '')]
    || 'Compass';
  const isDashboard = location.pathname === '/app' || location.pathname === '/app/';
  // founder_name (this component's own fetch) first, user?.name (AppContext)
  // as a fallback for the brief window before that fetch resolves -- see the
  // founderName state above for why AppContext alone was not reliable enough.
  const firstName = firstSafe([founderName, user?.name]).split(' ')[0] || 'there';

  return (
    <div className="platform" style={{ '--sb': sidebarCollapsed ? '68px' : '248px' }}>
      <aside className={`sidebar${sidebarOpen ? ' open' : ''}`} aria-label="Primary">
        <div className="sb-head">
          <div className="sb-head-top">
            {/* The lockup the marketing site uses: the Ally mark beside the
                product's own name -- the on-dark variant, since this sidebar is
                dark and the standard mark all but disappeared into it.
                product's own name. The wide GoXL wordmark that was here named
                the company, not the thing the founder is signed in to -- and
                nothing else in the sidebar said "Ally" at all. */}
            <div className="sb-brand">
              <img className="goxl-logo" src="/ally-logo-mark-on-dark.png" alt="" width="512" height="512" decoding="async" />
              <span className="sb-words">
                <span className="mark">GoXL <i>Ally</i></span>
                <span className="sub">by GoXL Entrepreneurship</span>
              </span>
            </div>
            <button
              className="sb-toggle"
              onClick={toggleSidebar}
              aria-expanded={!sidebarCollapsed}
              aria-label={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
              title={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            >
              <svg className="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M11 17l-5-5 5-5M18 17l-5-5 5-5" />
              </svg>
            </button>
          </div>
          <div className="ally-badge">
            <span className="dot" />
            Ally active
          </div>
        </div>

        <nav className="sb-nav" aria-label="Sections">
          {NAV_GROUPS.map((group) => (
            <div key={group.label}>
              {group.hideLabel
                ? <div className="sb-gap" aria-hidden="true" />
                : <div className="sb-group">{group.label}</div>}
              {group.items.map(({ path, action, tip, icon: Icon, label, badge, planBadge, needsReport, needsProfile, comingSoon, lockTip }) => {
                /* Only a founder who can actually upgrade is told to. */
                const itemBadge = planBadge ? (onTopTier ? null : 'Upgrade') : badge;
                const reportLocked = needsReport && !hasReport;
                const profileLocked = needsProfile && !profileComplete;
                const locked = reportLocked || profileLocked || comingSoon;
                return (
                  <button
                    key={path ?? action}
                    className={`nav-item${path && isActive(path) ? ' active' : ''}${locked ? ' locked' : ''}`}
                    data-tip={comingSoon ? (lockTip || 'Coming soon') : profileLocked ? 'Finish your profile to unlock' : reportLocked ? 'Finish your diagnosis to unlock' : path === '/app/vision' ? visionLabel(hasVision) : tip}
                    data-nav={path ?? action}
                    aria-disabled={reportLocked || profileLocked}
                    onClick={() => {
                      // A report-gated item sends them to the thing that
                      // unlocks it rather than an empty page they'd have to
                      // work out for themselves. A not-yet-built feature has
                      // nothing to unlock -- it opens its own honest
                      // "coming soon" page instead of redirecting anywhere.
                      /* Straight to the thing that unlocks it, same as the
                         report lock above -- not to a dead row. */
                      if (profileLocked) { handleNav('/guided/profile'); return; }
                      if (reportLocked) { handleNav('/app/founder-dna-journey'); return; }
                      // An action item stays put: the tour opens over whatever
                      // page they are on, and the drawer is left to the tour,
                      // which opens it itself on a phone.
                      if (action === 'tour') { startTour(); return; }
                      handleNav(path);
                    }}
                  >
                    <Icon className="ic" />
                    <span className="lbl">{path === '/app/vision' ? visionLabel(hasVision) : label}</span>
                    {locked && <IconLock className="nav-lock" />}
                    {!locked && itemBadge && <span className="nav-badge">{itemBadge}</span>}
                  </button>
                );
              })}
            </div>
          ))}
        </nav>

        <div className="sb-foot">
          <button className="sb-user" onClick={() => handleNav('/app/profile')}>
            {/* 'RV' was a mock founder's initials and 'Growth stage - founder' a
                placeholder, both shown to every real user under their own name.
                A real avatar (POST /profile/avatar, profile page) previously
                only ever showed on the profile page itself -- AppContext's
                user.avatar was hardcoded null, so the sidebar always fell back
                to initials even for a founder who had set a real photo. */}
            <div className="sb-av" style={user.avatar ? { padding: 0, overflow: 'hidden' } : undefined}>
              {user.avatar ? (
                <img src={user.avatar} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover', borderRadius: 'inherit' }} />
              ) : (
                user.initials || '?'
              )}
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div className="u-name">{user?.name || 'Your account'}</div>
              <div className="u-stage">{user?.email || 'View profile'}</div>
            </div>
            <svg className="u-cog" viewBox="0 0 24 24" fill="none" strokeWidth="1.7">
              <circle cx="12" cy="12" r="3" />
              <path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-2 2 2 2 0 01-2-2v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83 0 2 2 0 010-2.83l.06-.06A1.65 1.65 0 004.68 15a1.65 1.65 0 00-1.51-1H3a2 2 0 01-2-2 2 2 0 012-2h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 010-2.83 2 2 0 012.83 0l.06.06A1.65 1.65 0 009 4.68a1.65 1.65 0 001-1.51V3a2 2 0 012-2 2 2 0 012 2v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 0 2 2 0 010 2.83l-.06.06A1.65 1.65 0 0019.4 9a1.65 1.65 0 001.51 1H21a2 2 0 012 2 2 2 0 01-2 2h-.09a1.65 1.65 0 00-1.51 1z" />
            </svg>
          </button>
        </div>
      </aside>

      {/* Decorative: the drawer it backs is dismissed with Escape (below) and by
          the close button inside it, so this needs no role of its own. */}
      <div className={`scrim${sidebarOpen ? ' on' : ''}`} onClick={closeSidebar} aria-hidden="true" />

      <div className="main">
        <div className="topbar">
          <button className="tb-burger" onClick={openSidebar} aria-label="Open menu">
            <span /><span /><span />
          </button>
          <div className="tb-title">
            {isDashboard ? (
              <>
                <div className="ey">Overview</div>
                <h1>{greetingNow()}, {firstName}</h1>
              </>
            ) : (
              <>
                 <div className="ey">{ROUTE_EYE[location.pathname] || currentLabel}</div>
                 <h1>
                   {location.pathname === '/app/vision'
                     ? visionLabel(hasVision)
                     : location.pathname === '/app/report'
                     /* Matches the masthead on the report itself, which the
                        backend renders as "Founder Clarity Report · <date>"
                        (api/v1/reports/document.py), and the name the rest of
                        the product uses -- billing, the FAQs, the plan catalog
                        and the PDF all say Clarity Report.

                        It used to say "Founder DNA Report", which was a second
                        name for the same document AND collided with a real,
                        different thing: Founder DNA is its own nav page and a
                        section inside this report. */
                     ? 'Founder Clarity Report'
                     : location.pathname === '/app/next-steps'
                     ? 'Your next steps'
                     : location.pathname === '/app/discovery-call'
                     ? 'Book a discovery call'
                     : location.pathname === '/app/profile'
                     ? 'Founder Profile'
                     : currentLabel}
                 </h1>
              </>
            )}
          </div>
          <div className="tb-right">
            <button className="tb-pill" type="button" onClick={() => handleNav('/app/billing')}>
              <span className="tb-pill-dot" />
              {planLabel}
            </button>
            {/* The search button had no onClick and no target — a control that
                looked live and did nothing on every page. Removed until search
                exists rather than left as a dead affordance. */}
            <div style={{ position: 'relative' }} ref={npRef}>
              <button
                className="tb-icon"
                id="notifBell"
                type="button"
                aria-label={`Notifications${unreadCount ? `, ${unreadCount} unread` : ''}`}
                aria-expanded={npOpen}
                aria-controls="notif-panel"
                onClick={() => setNpOpen(o => !o)}
              >
                <IconBell />
                {unreadCount > 0 && <span className="n-badge" aria-hidden="true">{unreadCount}</span>}
              </button>
              {/* Panel was always in the DOM and merely hidden by the `on` class,
                  so its contents were read out on every page even when closed.
                  `inert` rather than `hidden` because it opens with an
                  opacity/transform transition that display:none would cancel. */}
              <div id="notif-panel" className={`np${npOpen ? ' on' : ''}`} inert={!npOpen}>
                <div className="np-head">
                  <div>
                    <div className="np-t">Ally Reminders</div>
                    <div className="np-sub">{unreadCount ? `${unreadCount} unread` : 'All caught up'}</div>
                  </div>
                  <button className="np-clear" onClick={clearNotifications} type="button"
                          disabled={!notifications.length}>Clear all</button>
                </div>
                <div className="np-list">
                  {notifications.length === 0 ? (
                    <div className="np-empty">
                      <div className="ne-ic">
                        <IconBell />
                      </div>
                      <b>You're all caught up</b>
                      <p>No pending reminders</p>
                    </div>
                  ) : notifications.map(n => {
                    /* A row with somewhere to go is a real button; one without
                       is a plain div. Rendering an unclickable thing as a
                       button is how a founder learns the panel does nothing. */
                    const go = () => {
                      if (n.unread) readNotification(n.id);
                      if (n.href) { handleNav(n.href); setNpOpen(false); }
                    };
                    const inner = (
                      <>
                        <div className="nr-rail"><div className="nr-dot" /></div>
                        <div className="nr-body">
                          <div className="nr-top">
                            {n.unread && <span className="nr-pill new">New</span>}
                            <span className="nr-time">{n.time}</span>
                          </div>
                          <div className="nr-msg">{n.title}</div>
                          {/* The sentence that says what to do about it. This
                              was being dropped entirely before. */}
                          {n.body && <div className="nr-sub">{n.body}</div>}
                        </div>
                      </>
                    );
                    return n.href ? (
                      <button
                        key={n.id}
                        className="nr nr-clickable"
                        type="button"
                        data-status={n.unread ? 'unread' : 'read'}
                        onClick={go}
                      >
                        {inner}
                      </button>
                    ) : (
                      <div key={n.id} className="nr" data-status={n.unread ? 'unread' : 'read'}>
                        {inner}
                      </div>
                    );
                  })}
                </div>
                <div className="np-foot">
                  {/* Was "View all in Plan", which sent a founder to Plan Your
                      Day whatever the notification was about -- a billing alert
                      included. Each row now goes to its own place, so the foot
                      just offers the one thing that applies to all of them. */}
                  {/* Mark all as read, NOT clear. These two buttons both called
                      clearNotifications, so "Clear all" at the top and "Mark all
                      as read" here did exactly the same thing -- and neither
                      cleared anything. */}
                  <button className="np-open" onClick={markAllNotificationsRead} type="button"
                          disabled={!unreadCount}>
                    <svg viewBox="0 0 24 24"><polyline points="20 6 9 17 4 12" /></svg>
                    Mark all as read
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div className="view-wrap">
          {/* overflowY:'hidden' overrides .view.active's own overflow-y:auto
              (from platform.css) specifically here -- #main-content just
              below is the real, more specific scroll owner for every /app/*
              page, and without this override the two competed for the same
              wheel/trackpad scroll exactly like .view-wrap did one layer out
              (already fixed). Scrollbar-drag still worked either way (it
              targets whichever element the mouse is directly over), which is
              why this surfaced as "the scrollbar works, the wheel doesn't"
              rather than a more obviously broken screen. Inline, not a CSS
              class change, because .view.active is also used on pages with
              no nested #main-content (guided onboarding) that still need to
              own their own scroll. */}
          <div className="view active" style={{ display: 'flex', flexDirection: 'column', flex: 1, minHeight: 0, overflowY: 'hidden' }}>
            <main id="main-content" tabIndex={-1} style={{ flex: 1, overflowY: 'auto', overflowX: 'hidden' }}>
              <Outlet />
            </main>
          </div>
        </div>
      </div>
      {/* Mounted here, not per-page: a pending deletion blocks every AI
          feature server-side, so the founder must meet it once on the way
          in rather than as a silent 403 somewhere deep in the product. */}
      <DeletionPendingGate />
      {/* After DeletionPendingGate: someone on their way out should not be
          asked to re-agree to anything first. That gate is undismissable, so
          it wins regardless; the order just makes the intent readable. */}
      <ReconsentGate />
      <PlanRequiredGate />
      <ProductTour />
      {/* Fixed-position, so it renders last and belongs to no column. */}
      <HelpWidget />
    </div>
  );
}


