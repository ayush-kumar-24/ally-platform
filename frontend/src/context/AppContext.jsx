import { createContext, useContext, useState, useCallback, useEffect } from 'react';
import { MOCK_FOUNDER } from '../data/mockData';
import { getAccessToken } from '../services/api';
import { getProfile } from '../services/profile';
import { listNotifications, markAllRead, toDisplay } from '../services/notifications';

const AppContext = createContext(null);

/** Server profile -> the shape the UI components already expect. */
function toUser(profile) {
  const name = profile?.full_name || '';
  return {
    ...MOCK_FOUNDER,          // keeps non-identity display defaults (avatar, etc.)
    name,
    initials: name.split(' ').filter(Boolean).slice(0, 2)
      .map(w => w[0].toUpperCase()).join('') || '?',
    email: profile?.email || '',
    company: profile?.business_name || '',
    plan: profile?.plan_type || 'free',
    founderId: profile?.founder_id ?? null,
  };
}

export function AppProvider({ children }) {
  // Identity starts empty, never as a mock founder. Rendering a fabricated name
  // ("Rahul Varma") to a signed-in founder is worse than rendering nothing for a
  // moment -- they cannot tell it is a placeholder.
  const [user, setUser] = useState(() => {
    const saved = localStorage.getItem('ally_founder');
    if (saved) { try { return JSON.parse(saved); } catch { /* fall through */ } }
    return toUser(null);
  });
  const [sidebarCollapsed, setSidebarCollapsed] = useState(
    () => localStorage.getItem('ally_sb_collapsed') === 'true'
  );
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [notifications, setNotifications] = useState([]);
  const [activeView, setActiveView] = useState('dashboard');
  const [isGuided, setIsGuided] = useState(false);
  const [guidedStage, setGuidedStage] = useState('');
  const [guidedProgress, setGuidedProgress] = useState(0);
  const [showMobileMenu, setShowMobileMenu] = useState(false);
  const [toast, setToast] = useState(null);
  const [tourOpen, setTourOpen] = useState(false);

  // Sync sidebar collapsed state → body.sb-collapsed class
  useEffect(() => {
    if (sidebarCollapsed) {
      document.body.classList.add('sb-collapsed');
    } else {
      document.body.classList.remove('sb-collapsed');
    }
    localStorage.setItem('ally_sb_collapsed', String(sidebarCollapsed));
  }, [sidebarCollapsed]);

  // Sync guided mode → body.guided class
  useEffect(() => {
    if (isGuided) {
      document.body.classList.add('guided');
    } else {
      document.body.classList.remove('guided');
    }
  }, [isGuided]);

  const toggleSidebar = useCallback(() => {
    setSidebarCollapsed(prev => !prev);
  }, []);

  const openSidebar = useCallback(() => setSidebarOpen(true), []);
  const closeSidebar = useCallback(() => setSidebarOpen(false), []);

  const showToast = useCallback((msg, duration = 3000) => {
    setToast(msg);
    setTimeout(() => setToast(null), duration);
  }, []);

  const navigate = useCallback((view) => {
    setActiveView(view);
    closeSidebar();
  }, [closeSidebar]);

  const startGuided = useCallback(() => {
    setIsGuided(true);
    setGuidedStage('login');
    setGuidedProgress(0);
  }, []);

  const goGuidedStep = useCallback((step, progress) => {
    setGuidedStage(step);
    if (progress !== undefined) setGuidedProgress(progress);
  }, []);

  const exitGuided = useCallback(() => {
    setIsGuided(false);
    setGuidedStage('');
    setActiveView('dashboard');
  }, []);

  const refreshNotifications = useCallback(() => {
    // AppProvider wraps the whole app, including the public landing page and the
    // pre-login guided screens. Without this guard, every anonymous visitor's
    // browser fired an authenticated request that could only ever fail --
    // wasted, and in dev mode it resolved to a nonexistent fixed founder and
    // came back 404 rather than a clean "not signed in."
    if (!getAccessToken()) return Promise.resolve();
    return listNotifications()
      .then(res => setNotifications((res?.items ?? []).map(toDisplay)))
      .catch(() => { /* the bell is not worth failing a page over */ });
  }, []);

  useEffect(() => { refreshNotifications(); }, [refreshNotifications]);

  // "Clear all" must reach the server, otherwise the notifications return on the
  // next load and the button looks broken.
  const clearNotifications = useCallback(() => {
    setNotifications([]);
    markAllRead().catch(() => refreshNotifications());
  }, [refreshNotifications]);

  const startTour = useCallback(() => setTourOpen(true), []);
  const endTour = useCallback(() => setTourOpen(false), []);

  // Hydrate identity from the server. localStorage is only a first-paint cache --
  // the server is the truth, so a name changed elsewhere (or a stale cache from a
  // previous account on this browser) is corrected on load rather than persisting.
  useEffect(() => {
    if (!getAccessToken()) return undefined;
    let cancelled = false;
    getProfile()
      .then(p => { if (!cancelled && p) setUser(toUser(p)); })
      .catch(() => { /* signed out or offline: keep the cached value */ });
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    if (user) {
      localStorage.setItem('ally_founder', JSON.stringify(user));
    }
  }, [user]);

  return (
    <AppContext.Provider value={{
      user, setUser,
      sidebarCollapsed, toggleSidebar,
      sidebarOpen, openSidebar, closeSidebar,
      notifications, setNotifications, clearNotifications, refreshNotifications,
      activeView, setActiveView: navigate,
      isGuided, setIsGuided,
      guidedStage, setGuidedStage: goGuidedStep,
      guidedProgress, setGuidedProgress,
      showMobileMenu, setShowMobileMenu,
      toast, showToast,
      startGuided, exitGuided,
      navigate,
      tourOpen, startTour, endTour,
    }}>
      {children}
    </AppContext.Provider>
  );
}

export function useApp() {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error('useApp must be used within AppProvider');
  return ctx;
}
