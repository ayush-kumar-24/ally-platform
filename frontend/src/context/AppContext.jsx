// Both sides are needed: useRef + planning for the task-reminder nudges from
// main, and the real profile/notification services from feat/admin-panel.
// mockData is deliberately gone -- see toUser below.
import { createContext, useContext, useState, useCallback, useEffect, useRef } from 'react';
import { getAccessToken } from '../services/api';
import { getProfile } from '../services/profile';
import { listNotifications, markAllRead, toDisplay } from '../services/notifications';
import { isDueOrOverdue, listTasks } from '../services/planning';

const AppContext = createContext(null);

/** Server profile -> the shape the UI components already expect.
 *
 * This used to spread MOCK_FOUNDER "for display defaults". Those defaults were
 * a fictional person: it gave every signed-in founder stage "Early Traction", a
 * clarity score of 72, the role "CEO & Co-founder", a location in Mumbai and
 * the label "Pro" regardless of what they actually pay. Nothing reads those
 * fields any more, and a real founder must not inherit a fake one's details.
 */
function toUser(profile) {
  const name = profile?.full_name || '';
  return {
    avatar: null,
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

  /* The timer was neither tracked nor cleared: a second toast within the
     3s window inherited the first one's pending timeout and vanished early,
     and the last timer outlived unmount. */
  const toastTimer = useRef(null);
  useEffect(() => () => clearTimeout(toastTimer.current), []);

  const showToast = useCallback((msg, duration = 3000) => {
    clearTimeout(toastTimer.current);
    setToast(msg);
    toastTimer.current = setTimeout(() => setToast(null), duration);
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

  // Ally nudges the founder about overdue/due-today plan tasks while they're
  // active in the app -- there's no backend delivery worker for this (the
  // reminders table exists but nothing polls it yet), so this is a client-side
  // stand-in: check once on load, then periodically while the tab stays open.
  // A ref (not state) tracks which task ids have already been surfaced this
  // session, so the same overdue task doesn't re-toast every interval.
  const remindedTaskIds = useRef(new Set());
  const checkTaskReminders = useCallback(async () => {
    // AppContext wraps the whole app, including the public marketing/landing
    // page -- without this guard, every anonymous visitor's browser fired a
    // GET /planning/plans on load. Live-confirmed on production: the backend
    // answers that unauthenticated call with a raw 500 (should be 401), so
    // this was not just wasted traffic but a real, always-on production
    // error for every single landing-page visit. The catch below already
    // intended "no session yet" to be silent -- skipping the call entirely
    // for a signed-out visitor gets the same outcome without ever making it.
    if (!getAccessToken()) return;
    let tasks;
    try {
      tasks = await listTasks();
    } catch {
      // Session expired between mount and this call, feature not on this
      // plan (403), or offline -- silent, same as the /profile fetch above.
      // Not an error worth surfacing here.
      return;
    }
    const due = tasks.filter(isDueOrOverdue).filter(t => !remindedTaskIds.current.has(t.task_id));
    if (due.length === 0) return;
    due.forEach(t => remindedTaskIds.current.add(t.task_id));
    const [first, ...rest] = due;
    const message = rest.length === 0
      ? `Reminder: "${first.title}" is due.`
      : `Reminder: "${first.title}" and ${rest.length} other task${rest.length > 1 ? 's' : ''} due.`;
    showToast(message, 6000);
  }, [showToast]);

  useEffect(() => {
    checkTaskReminders();
    const interval = setInterval(checkTaskReminders, 20 * 60 * 1000); // every 20 min while active
    return () => clearInterval(interval);
  }, [checkTaskReminders]);

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
