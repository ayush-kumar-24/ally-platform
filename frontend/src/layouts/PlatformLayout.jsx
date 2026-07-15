import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import { useApp } from '../context/AppContext';
import { useState, useRef, useEffect } from 'react';
import {
  IconDashboard,
  IconMessageSquare,
  IconUser,
  IconTrendingUp,
  IconDocument,
  IconArrowRight,
  IconCalendar,
  IconHelpCircle,
  IconSettings,
  IconSearch,
  IconBell,
  IconPlus,
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
  '/app/diagnosis': 'Diagnosis',
  '/app/founder-dna': 'Founder first',
  '/app/business-dna': 'Business',
  '/app/report': 'Executive report',
  '/app/next-steps': 'Momentum',
  '/app/plan': 'Today',
  '/app/discovery-call': 'Talk to a human',
  '/app/profile': 'Founder identity',
  '/app/help': "We're here to help",
};

const NAV_GROUPS = [
  {
    label: 'HOME',
    items: [
      { path: '/app', tip: 'Dashboard', icon: IconDashboard, label: 'Dashboard', badge: null },
      { path: '/app/ally-chat', tip: 'Chat with Ally', icon: IconMessageSquare, label: 'Chat with Ally', badge: null },
    ],
  },
  {
    label: 'FOUNDER DIAGNOSIS',
    items: [
      { path: '/app/diagnosis', tip: 'Adaptive diagnosis', icon: IconPulse, label: 'Adaptive diagnosis', badge: null },
      { path: '/app/founder-dna', tip: 'Founder DNA', icon: IconUser, label: 'Founder DNA', badge: null },
      { path: '/app/business-dna', tip: 'Business DNA', icon: IconTrendingUp, label: 'Business DNA', badge: null },
      { path: '/app/report', tip: 'Report', icon: IconDocument, label: 'Report', badge: null },
      { path: '/app/next-steps', tip: 'Next steps', icon: IconArrowRight, label: 'Next steps', badge: null },
      { path: '/app/plan', tip: 'Plan Your Day', icon: IconCalendar, label: 'Plan Your Day', badge: 3 },
      { path: '/app/discovery-call', tip: 'Discovery call', icon: IconCalendar, label: 'Discovery call', badge: null },
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
  const nav = useNavigate();
  const location = useLocation();
  const [npOpen, setNpOpen] = useState(false);
  const npRef = useRef(null);

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

  const isActive = (path) => {
    if (path === '/app') return location.pathname === '/app' || location.pathname === '/app/';
    return location.pathname.startsWith(path);
  };

  const currentLabel = NAV_GROUPS.flatMap(g => g.items).find(i => isActive(i.path))?.label || 'Dashboard';
  const isDashboard = location.pathname === '/app' || location.pathname === '/app/';
  const firstName = (user?.name || 'Ayush Sharma').split(' ')[0];

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
              {group.items.map(({ path, tip, icon: Icon, label, badge }) => (
                <button
                  key={path}
                  className={`nav-item${isActive(path) ? ' active' : ''}`}
                  data-tip={tip}
                  data-nav={path}
                  onClick={() => handleNav(path)}
                >
                  <Icon className="ic" />
                  <span className="lbl">{label}</span>
                  {badge && <span className="nav-badge">{badge}</span>}
                </button>
              ))}
            </div>
          ))}
        </nav>

        <div className="nav-upsell">
          <div className="nu-t">* <span>Ally Free</span></div>
          <div className="nu-s">Unlock deeper diagnosis, unlimited chat and Founder MRI.</div>
          <button className="nu-btn" onClick={() => handleNav('/app/billing')}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M12 19V5M5 12l7-7 7 7" />
            </svg>
            Upgrade plan
          </button>
        </div>

        <div className="sb-foot">
          <button className="sb-user" onClick={() => handleNav('/app/profile')}>
            <div className="sb-av">{user.initials || 'RV'}</div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div className="u-name">{user.name || 'Rahul Varma'}</div>
              <div className="u-stage">Growth stage - founder</div>
            </div>
            <svg className="u-cog" viewBox="0 0 24 24" fill="none" strokeWidth="1.7">
              <circle cx="12" cy="12" r="3" />
              <path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-2 2 2 2 0 01-2-2v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83 0 2 2 0 010-2.83l.06-.06A1.65 1.65 0 004.68 15a1.65 1.65 0 00-1.51-1H3a2 2 0 01-2-2 2 2 0 012-2h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 010-2.83 2 2 0 012.83 0l.06.06A1.65 1.65 0 009 4.68a1.65 1.65 0 001-1.51V3a2 2 0 012-2 2 2 0 012 2v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 0 2 2 0 010 2.83l-.06.06A1.65 1.65 0 0019.4 9a1.65 1.65 0 001.51 1H21a2 2 0 012 2 2 2 0 01-2 2h-.09a1.65 1.65 0 00-1.51 1z" />
            </svg>
          </button>
        </div>
      </aside>

      <div className={`scrim${sidebarOpen ? ' on' : ''}`} onClick={closeSidebar} />

      <div className="main">
        <div className="topbar">
          <button className="tb-burger" onClick={openSidebar} aria-label="Open menu">
            <span /><span /><span />
          </button>
          <div className="tb-title">
            {isDashboard ? (
              <>
                <div className="ey">Overview</div>
                <h1>Good morning, {firstName}</h1>
              </>
            ) : (
              <>
                 <div className="ey">{ROUTE_EYE[location.pathname] || currentLabel}</div>
                 <h1>
                   {location.pathname === '/app/report'
                     ? 'Founder DNA Report'
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
              Ally Free
            </button>
            <button className="tb-icon" type="button" aria-label="Search">
              <IconSearch />
            </button>
            <div style={{ position: 'relative' }} ref={npRef}>
              <button className="tb-icon" id="notifBell" onClick={() => setNpOpen(o => !o)} aria-label="Notifications" type="button">
                <IconBell />
                {notifications.length > 0 && <span className="n-badge">{notifications.length}</span>}
              </button>
              <div className={`np${npOpen ? ' on' : ''}`}>
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
            <button className="btn btn-primary tb-cta" onClick={() => handleNav('/app/diagnosis')} type="button">
              <IconPlus />
              New diagnosis
            </button>
          </div>
        </div>

        <div className="view-wrap">
          <div className="view active" style={{ display: 'flex', flexDirection: 'column', flex: 1, minHeight: 0 }}>
            <main style={{ flex: 1, overflowY: 'auto', overflowX: 'hidden' }}>
              <Outlet />
            </main>
          </div>
        </div>
      </div>
    </div>
  );
}


