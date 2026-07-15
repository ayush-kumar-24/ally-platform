import { createContext, useContext, useState, useCallback, useEffect } from 'react';
import { MOCK_FOUNDER, MOCK_NOTIFICATIONS } from '../data/mockData';

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

  useEffect(() => {
    const saved = localStorage.getItem('ally_founder');
    if (saved) {
      try { setUser(JSON.parse(saved)); } catch (e) {}
    }
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
      notifications, setNotifications, clearNotifications,
      activeView, setActiveView: navigate,
      isGuided, setIsGuided,
      guidedStage, setGuidedStage: goGuidedStep,
      guidedProgress, setGuidedProgress,
      showMobileMenu, setShowMobileMenu,
      toast, showToast,
      startGuided, exitGuided,
      navigate,
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
