/**
 * Admin shell — nav + the signed-in admin's identity.
 *
 * Nav links are filtered by capability so staff aren't shown pages that would only
 * 403. That is presentation only: the backend authorizes every request regardless
 * of what this renders.
 */

import { useEffect, useState } from 'react';
import { NavLink, Outlet } from 'react-router-dom';
import { getMe } from '../../services/admin';
import { ErrorState, Loading } from './AdminUI';
import '../../styles/admin.css';

const LINKS = [
  { to: '/admin', label: 'Dashboard', end: true, capability: 'view_users' },
  { to: '/admin/users', label: 'Users', capability: 'view_users' },
  { to: '/admin/usage', label: 'Usage', capability: 'view_users' },
  { to: '/admin/audit', label: 'Audit Log', capability: 'view_audit' },
  { to: '/admin/system', label: 'System', capability: 'view_users' },
];

export default function AdminLayout() {
  const [me, setMe] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  const load = () => {
    setLoading(true);
    setError(null);
    getMe()
      .then(setMe)
      .catch(setError)
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  /* The loading and error branches returned a bare <div>, so on those states —
     which is what anyone without admin access, or anyone hitting a backend
     outage, actually sees — the page had no main landmark and no h1 for the
     skip link or a landmark menu to target. */
  if (loading) {
    return (
      <div className="adm">
        <main id="main-content" tabIndex={-1} className="adm-main">
          <h1 className="sr-only">Ally Admin</h1>
          <Loading label="Checking admin access…" />
        </main>
      </div>
    );
  }
  if (error) {
    // A non-admin lands here. Say so plainly rather than rendering an empty shell.
    return (
      <div className="adm">
        <main id="main-content" tabIndex={-1} className="adm-main">
          <h1 className="sr-only">Ally Admin</h1>
          <ErrorState error={error} onRetry={load} />
        </main>
      </div>
    );
  }

  const visible = LINKS.filter(l => me?.capabilities?.includes(l.capability));

  return (
    <div className="adm">
      <header className="adm-topbar">
        <h1 className="adm-brand">Ally Admin</h1>
        <span className="adm-badge">Internal</span>
        <nav className="adm-nav">
          {visible.map(l => (
            <NavLink key={l.to} to={l.to} end={l.end}
                     className={({ isActive }) => (isActive ? 'active' : '')}>
              {l.label}
            </NavLink>
          ))}
        </nav>
        <span className="adm-whoami">
          {me.email} · {me.role.replace('_', ' ')}
        </span>
      </header>
      <main id="main-content" tabIndex={-1} className="adm-main">
        <Outlet context={{ me }} />
      </main>
    </div>
  );
}
