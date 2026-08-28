import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import DeletionPendingGate from '../components/DeletionPendingGate';
import { useApp } from '../context/AppContext';
import { useState, useRef, useEffect } from 'react';
import ProductTour from '../components/ProductTour';
import { TITLES as ROUTE_TITLES } from '../components/RouteTitle';
import { greetingNow } from '../utils/helpers';
import { getOverview } from '../services/dashboard';
import { firstSafe } from '../utils/looksLikeToken';
import { useCallAccess } from '../hooks/useCallAccess';
import {
  IconDashboard,
  IconMessageSquare,
  IconUser,
  IconTrendingUp,
  IconDocument,
  IconLock,
  IconArrowRight,
  IconCalendar,
  IconHelpCircle,
  IconSettings,
  IconBell,
  IconEye,
  IconMapPin,
  IconAward,
  IconList,
  IconLightbulb,
  IconBook,
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
  '/app/diagnosis': 'Diagnosis',
  '/app/founder-dna': 'Founder first',
  '/app/vision': 'Long-term',
  '/app/business-dna': 'Business',
  '/app/journey': 'Momentum',
  '/app/achievements': 'Milestones',
  '/app/goals': 'Outcomes',
  '/app/recommendations': 'What to do next',
  '/app/frameworks': 'Thinking toolkit',
  '/app/report': 'Executive report',
  '/app/next-steps': 'Momentum',
  '/app/plan': 'Today',
  '/app/discovery-call': 'Talk to a human',
  '/app/feedback': 'Tell us what you think',
  '/app/profile': 'Founder identity',
  '/app/help': "We're here to help",
};

const NAV_GROUPS = [
  {
    label: 'HOME',
    items: [
      { path: '/app', tip: 'Compass', icon: IconDashboard, label: 'Compass', badge: null },
      { path: '/app/ally-chat', tip: 'Talk to Ally', icon: IconMessageSquare, label: 'Talk to Ally', badge: null },
    ],
  },
  {
    label: 'FOUNDER DIAGNOSIS',
    items: [
      /* Ordered to read as the journey itself: Founder DNA, then Business DNA,
         then the diagnosis that uses both. That is the sequence a founder is
         actually taken through, and the nav is the only place it is visible.
         (2026-08-27 product decision.)

         Worth knowing when reading this list: the first two are the RESULT
         pages, written *from* a finished diagnosis, while "Adaptive diagnosis"
         below is the entry point that runs all three phases. So for a founder
         with no report yet, the two items above the entry point are locked --
         the order tells them what they are working toward, not what to click
         first. If that ever reads as friction rather than a map, the fix is to
         surface the entry point separately, not to reshuffle these again. */
      { path: '/app/founder-dna', tip: 'Founder DNA', icon: IconUser, label: 'Founder DNA', badge: null, needsReport: true },
      { path: '/app/business-dna', tip: 'Business DNA', icon: IconTrendingUp, label: 'Business DNA', badge: null, needsReport: true },
      { path: '/app/founder-dna-journey', tip: 'Adaptive diagnosis', icon: IconPulse, label: 'Adaptive diagnosis', badge: null },
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
      /* Hidden outright rather than locked, unlike needsReport above. A locked
         item still advertises the feature; for the beta the instruction is to
         take discovery calls out of the free-tier UI, and a founder who cannot
         book one has nothing to unlock by clicking. */
      { path: '/app/discovery-call', tip: 'Discovery call', icon: IconCalendar, label: 'Discovery call', badge: null, needsCallAccess: true },
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
      { path: '/app/help', tip: 'Help & Support', icon: IconHelpCircle, label: 'Help & Support', badge: null },
    ],
  },
];

export default function PlatformLayout() {
  const { user, sidebarCollapsed, toggleSidebar, sidebarOpen, openSidebar, closeSidebar, notifications, clearNotifications } = useApp();

  // Both of these read "Ally Free" as literal text, so a paying founder was shown
  // the free badge everywhere. `user.plan` is hydrated from the server profile.
  const planTier = (user?.plan || 'free').toLowerCase();
  const planLabel = { free: 'Ally Free', starter: 'Ally Starter', pro: 'Ally Pro' }[planTier]
    || `Ally ${planTier.charAt(0).toUpperCase()}${planTier.slice(1)}`;
  const onTopTier = planTier === 'pro';
  const nav = useNavigate();
  const location = useLocation();
  const [npOpen, setNpOpen] = useState(false);
  const npRef = useRef(null);

  /* Whether a diagnosis has actually produced a report yet -- what decides
     which nav items are still locked. Starts unlocked so a slow call never
     shuts a founder out of pages they have already earned. */
  // Discovery calls are hidden for founders with no free call left -- see
  // hooks/useCallAccess for why the plan feature flag is the wrong signal.
  const { canBook: canBookCall } = useCallAccess();

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
            <div className="sb-brand">
              <img className="goxl-logo" src="/goxl-logo.svg" alt="GoXL" width="2515" height="755" decoding="async" />
              <span className="sub">Consulting Solutions</span>
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
              <div className="sb-group">{group.label}</div>
              {group.items.map(({ path, tip, icon: Icon, label, badge, needsReport, needsCallAccess, comingSoon, lockTip }) => {
                if (needsCallAccess && !canBookCall) return null;
                const reportLocked = needsReport && !hasReport;
                const locked = reportLocked || comingSoon;
                return (
                  <button
                    key={path}
                    className={`nav-item${isActive(path) ? ' active' : ''}${locked ? ' locked' : ''}`}
                    data-tip={comingSoon ? (lockTip || 'Coming soon') : reportLocked ? 'Finish your diagnosis to unlock' : tip}
                    data-nav={path}
                    aria-disabled={reportLocked}
                    onClick={() => {
                      // A report-gated item sends them to the thing that
                      // unlocks it rather than an empty page they'd have to
                      // work out for themselves. A not-yet-built feature has
                      // nothing to unlock -- it opens its own honest
                      // "coming soon" page instead of redirecting anywhere.
                      if (reportLocked) { handleNav('/app/founder-dna-journey'); return; }
                      handleNav(path);
                    }}
                  >
                    <Icon className="ic" />
                    <span className="lbl">{label}</span>
                    {locked && <IconLock className="nav-lock" />}
                    {!locked && badge && <span className="nav-badge">{badge}</span>}
                  </button>
                );
              })}
            </div>
          ))}
        </nav>

        <div className="nav-upsell">
          {/* The leading "*" was a stand-in for a dropped icon and was read out
              as "asterisk" before the plan name on every page. */}
          <div className="nu-t"><span>{planLabel}</span></div>
          <div className="nu-s">Unlock deeper diagnosis, unlimited chat and Founder MRI.</div>
          <button className="nu-btn" onClick={() => handleNav('/app/billing')}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M12 19V5M5 12l7-7 7 7" />
            </svg>
            {onTopTier ? 'Manage plan' : 'Upgrade plan'}
          </button>
        </div>

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
                   {location.pathname === '/app/report'
                     ? 'Founder DNA Report'
                     : location.pathname === '/app/next-steps'
                     ? 'Your next steps'
                     /* The page is still reachable by URL when booking is not
                        available, and titling it "Book a..." above a card that
                        explains they cannot book is the same overclaim this
                        change is removing. */
                     : location.pathname === '/app/discovery-call'
                     ? (canBookCall ? 'Book a discovery call' : 'Discovery call')
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
                aria-label={`Notifications${notifications.length ? `, ${notifications.length} unread` : ''}`}
                aria-expanded={npOpen}
                aria-controls="notif-panel"
                onClick={() => setNpOpen(o => !o)}
              >
                <IconBell />
                {notifications.length > 0 && <span className="n-badge" aria-hidden="true">{notifications.length}</span>}
              </button>
              {/* Panel was always in the DOM and merely hidden by the `on` class,
                  so its contents were read out on every page even when closed.
                  `inert` rather than `hidden` because it opens with an
                  opacity/transform transition that display:none would cancel. */}
              <div id="notif-panel" className={`np${npOpen ? ' on' : ''}`} inert={!npOpen}>
                <div className="np-head">
                  <div>
                    <div className="np-t">Ally Reminders</div>
                    <div className="np-sub">{notifications.length} active</div>
                  </div>
                  <button className="np-clear" onClick={clearNotifications} type="button">Clear all</button>
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
                  ) : notifications.map(n => (
                    <div key={n.id} className="nr" data-status={n.status}>
                      <div className="nr-rail"><div className="nr-dot" /></div>
                      <div className="nr-body">
                        <div className="nr-top">
                          <span className={`nr-pill ${n.status}`}>{n.status}</span>
                          <span className="nr-time">{n.time}</span>
                        </div>
                        <div className="nr-msg">{n.message}</div>
                      </div>
                    </div>
                  ))}
                </div>
                <div className="np-foot">
                  <button className="np-open" onClick={() => { handleNav('/app/plan'); setNpOpen(false); }} type="button">
                    <svg viewBox="0 0 24 24"><rect x="3" y="4" width="18" height="18" rx="2" /><line x1="16" y1="2" x2="16" y2="6" /><line x1="8" y1="2" x2="8" y2="6" /><line x1="3" y1="10" x2="21" y2="10" /></svg>
                    View all in Plan
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
      <ProductTour />
    </div>
  );
}


