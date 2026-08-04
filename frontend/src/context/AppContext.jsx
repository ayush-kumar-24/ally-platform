import { createContext, useContext, useState, useCallback, useEffect, useRef } from 'react';
import { MOCK_FOUNDER, MOCK_NOTIFICATIONS } from '../data/mockData';
import { get } from '../services/api';
import { isDueOrOverdue, listTasks } from '../services/planning';

const AppContext = createContext(null);

export function AppProvider({ children }) {
  const [user, setUser] = useState(MOCK_FOUNDER);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(
    () => localStorage.getItem('ally_sb_collapsed') === 'true'
  );
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [notifications, setNotifications] = useState(MOCK_NOTIFICATIONS);
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

  const clearNotifications = useCallback(() => {
    setNotifications([]);
  }, []);

  const startTour = useCallback(() => setTourOpen(true), []);
  const endTour = useCallback(() => setTourOpen(false), []);

  useEffect(() => {
    const saved = localStorage.getItem('ally_founder');
    if (saved) {
      try { setUser(JSON.parse(saved)); } catch (e) {}
    }
  }, []);

  // Real plan_type from the backend -- the source of truth for plan-gated
  // features (e.g. voice input in chat). Merged onto the existing user object
  // rather than replacing it: most of `user` today (stage, company, clarityScore,
  // ...) still comes from mock data / other screens, and isn't part of this fetch.
  useEffect(() => {
    get('/profile')
      .then((profile) => {
        setUser((prev) => ({
          ...prev,
          founder_id: profile.founder_id,
          plan_type: profile.plan_type,
          name: profile.full_name || prev?.name,
        }));
      })
      .catch(() => {
        // No session yet / backend unreachable -- keep whatever's in `user`
        // (mock or localStorage). If plan_type ends up missing, the UI-level
        // gate (canUseVoiceInChat) can't pre-block, but the backend's own
        // check on POST /voice/transcribe is the real authority and still
        // enforces the free-plan restriction regardless of frontend state.
      });
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
    let tasks;
    try {
      tasks = await listTasks();
    } catch {
      // No session yet, feature not on this plan (403), or offline -- silent,
      // same as the /profile fetch above. Not an error worth surfacing here.
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
      notifications, setNotifications, clearNotifications,
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
