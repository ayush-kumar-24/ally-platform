import { lazy, Suspense, useEffect, useState } from 'react';
import { Routes, Route, Navigate, useNavigate } from 'react-router-dom';
import { useApp } from './context/AppContext';
import { clearTokens, onAuthFailure } from './services/api';
import { startDevSession } from './services/auth';
import { supabaseConfigured } from './services/supabaseConfig';
import { loadChunk } from './utils/loadChunk';
import ErrorBoundary from './components/ErrorBoundary';
import RequireAuth from './components/RequireAuth';
import RouteTitle from './components/RouteTitle';
import SplashScreen from './components/SplashScreen';
import Toast from './components/ui/Toast';
import CookieBanner from './components/CookieBanner';

/* Landing and Login stay in the main chunk: they are the two entry points, and
   a lazy boundary on either would trade a 30 kB saving for a blank frame on the
   very first paint. Everything below is behind a route the visitor navigates to,
   so its chunk downloads while they are still reading the page before it. This
   took the initial bundle from 827 kB to a fraction of that -- see the route
   chunks in `npm run build`. */
import LandingLayout from './layouts/LandingLayout';
import LandingPage from './pages/LandingPage';
import GuidedLayout from './layouts/GuidedLayout';
import Login from './pages/guided/Login';
import NotFound from './pages/NotFound';

const PlatformLayout = lazy(() => loadChunk(() => import('./layouts/PlatformLayout')));

const Resume = lazy(() => loadChunk(() => import('./pages/guided/Resume')));
const Expectation = lazy(() => loadChunk(() => import('./pages/guided/Expectation')));
const Welcome = lazy(() => loadChunk(() => import('./pages/guided/Welcome')));
const AllyIntro = lazy(() => loadChunk(() => import('./pages/guided/AllyIntro')));
const ProfileBuild = lazy(() => loadChunk(() => import('./pages/guided/ProfileBuild')));
const Tour = lazy(() => loadChunk(() => import('./pages/guided/Tour')));
const Summary = lazy(() => loadChunk(() => import('./pages/guided/Summary')));
const Validate = lazy(() => loadChunk(() => import('./pages/guided/Validate')));
const Problem = lazy(() => loadChunk(() => import('./pages/guided/Problem')));

const Dashboard = lazy(() => loadChunk(() => import('./pages/Dashboard')));
const AllyChat = lazy(() => loadChunk(() => import('./pages/AllyChat')));
const DiagnosisChat = lazy(() => loadChunk(() => import('./pages/DiagnosisChat')));
const FounderDnaChat = lazy(() => loadChunk(() => import('./pages/FounderDnaChat')));
const CurrentProblemChat = lazy(() => loadChunk(() => import('./pages/CurrentProblemChat')));
const Thinking = lazy(() => loadChunk(() => import('./pages/Thinking')));
const FounderProfile = lazy(() => loadChunk(() => import('./pages/FounderProfile')));
const FounderDNA = lazy(() => loadChunk(() => import('./pages/FounderDNA')));
const VisionPage = lazy(() => loadChunk(() => import('./pages/VisionPage')));
const JourneyPage = lazy(() => loadChunk(() => import('./pages/JourneyPage')));
const AchievementsPage = lazy(() => loadChunk(() => import('./pages/AchievementsPage')));
const GoalsPage = lazy(() => loadChunk(() => import('./pages/GoalsPage')));
const RecommendationsPage = lazy(() => loadChunk(() => import('./pages/RecommendationsPage')));
const FrameworksPage = lazy(() => loadChunk(() => import('./pages/FrameworksPage')));
const FrameworkDetail = lazy(() => loadChunk(() => import('./pages/FrameworkDetail')));
const BusinessDNA = lazy(() => loadChunk(() => import('./pages/BusinessDNA')));
const NextSteps = lazy(() => loadChunk(() => import('./pages/NextSteps')));
const DiscoveryCall = lazy(() => loadChunk(() => import('./pages/DiscoveryCall')));
const PlanYourDay = lazy(() => loadChunk(() => import('./pages/PlanYourDay')));
const KnowMyEnergy = lazy(() => loadChunk(() => import('./pages/KnowMyEnergy')));
const Report = lazy(() => loadChunk(() => import('./pages/Report')));
const Billing = lazy(() => loadChunk(() => import('./pages/Billing')));
const HelpSupport = lazy(() => loadChunk(() => import('./pages/HelpSupport')));
const Feedback = lazy(() => loadChunk(() => import('./pages/Feedback')));
const TermsOfService = lazy(() => loadChunk(() => import('./pages/TermsOfService')));
const PrivacyPolicy = lazy(() => loadChunk(() => import('./pages/PrivacyPolicy')));

// Admin Panel — internal only. Access is decided by the backend (/admin/me);
// AdminLayout renders an access error for anyone the server does not recognise.
const AdminLayout = lazy(() => loadChunk(() => import('./pages/admin/AdminLayout')));
const AdminDashboard = lazy(() => loadChunk(() => import('./pages/admin/AdminDashboard')));
const AdminUsers = lazy(() => loadChunk(() => import('./pages/admin/AdminUsers')));
const AdminUserDetail = lazy(() => loadChunk(() => import('./pages/admin/AdminUserDetail')));
const AdminAuditLog = lazy(() => loadChunk(() => import('./pages/admin/AdminAuditLog')));
const AdminSystem = lazy(() => loadChunk(() => import('./pages/admin/AdminSystem')));
const AdminUsage = lazy(() => loadChunk(() => import('./pages/admin/AdminUsage')));

/* Show splash only once per session (won't replay on route changes).
   Wrapped because storage access throws outright -- not returns null -- in
   Safari's Lock Mode and in any embedded/third-party context where cookies are
   blocked. At module scope that exception escapes before React mounts, so the
   whole app renders a blank page rather than just losing the splash. */
function splashAlreadyShown() {
  try {
    return sessionStorage.getItem('splashShown') === 'true';
  } catch {
    return true;
  }
}

/* Route chunks are small and served from the same origin, so this is visible
   for a frame or two at most -- long enough to avoid a flash of nothing, short
   enough that a spinner would be more distracting than the blank it replaces. */
function RouteFallback() {
  return <div style={{ minHeight: '100dvh', background: 'var(--color-forest-night, #06140d)' }} />;
}

export default function App() {
  const { toast } = useApp();
  const [showSplash, setShowSplash] = useState(!splashAlreadyShown());
  const navigate = useNavigate();

  // A session that can't be recovered (no refresh token, or the server rejects
  // it) used to fail every request silently on whatever page the founder was
  // on -- each page showing its own generic "couldn't reach the server"
  // message, which reads as a network problem rather than "please sign in
  // again." This sends them to login instead, which is what actually fixes it.
  useEffect(() => {
    onAuthFailure(async () => {
      /* Local development has no Supabase, so "sign in again" means clicking
         through the login page to re-mint the same dev session -- which is
         exactly what happens automatically here instead. Access tokens last 30
         minutes, and walking the guided flow at reading speed takes longer than
         that, so without this a founder gets dumped back at login mid-journey
         and loses their place. Never runs in production, where Supabase is
         configured and a real sign-in is genuinely required. */
      if (!supabaseConfigured) {
        try {
          if (await startDevSession()) return;
        } catch { /* fall through to the real sign-out below */ }
      }
      clearTokens();
      localStorage.removeItem('ally_founder');
      navigate('/guided/login', { replace: true });
    });
  }, [navigate]);

  const handleSplashDone = () => {
    try { sessionStorage.setItem('splashShown', 'true'); } catch { /* see above */ }
    setShowSplash(false);
  };

  return (
    <>
      {/* First focusable thing on every route. Every /app/* screen puts a
          12-item sidebar and a topbar ahead of the content; without this a
          keyboard or screen-reader user tabs through all of it on every
          navigation. */}
      <a href="#main-content" className="skip-link">Skip to main content</a>
      <RouteTitle />
      {showSplash && <SplashScreen onDone={handleSplashDone} />}
      <Suspense fallback={<RouteFallback />}>
        <Routes>
          {/* ── Landing ── */}
          <Route element={
            <ErrorBoundary label="Landing" fallbackPath="/">
              <LandingLayout />
            </ErrorBoundary>
          }>
            <Route path="/" element={<LandingPage />} />
          </Route>

          {/* ── Legal pages ── */}
          <Route path="/terms" element={
            <ErrorBoundary label="Terms of Service" fallbackPath="/">
              <TermsOfService />
            </ErrorBoundary>
          } />
          <Route path="/privacy" element={
            <ErrorBoundary label="Privacy Policy" fallbackPath="/">
              <PrivacyPolicy />
            </ErrorBoundary>
          } />

          {/* ── Guided onboarding ── */}
          <Route path="/guided" element={
            <ErrorBoundary label="Guided Onboarding" fallbackPath="/">
              <GuidedLayout />
            </ErrorBoundary>
          }>
            <Route index element={<Navigate to="login" replace />} />
            <Route path="login" element={<Login />} />
            <Route path="resume" element={<Resume />} />
            <Route path="expectation" element={<Expectation />} />
            <Route path="welcome" element={<Welcome />} />
            <Route path="ally-intro" element={<AllyIntro />} />
            <Route path="profile" element={<ProfileBuild />} />
            <Route path="tour" element={<Tour />} />
            <Route path="summary" element={<Summary />} />
            <Route path="validate" element={<Validate />} />
            <Route path="problem" element={<Problem />} />
            {/* reveal / root-cause / conclusion / report used to sit here: a fully
                scripted "Ally reasons through your problem" sequence with fixed
                dialogue and a fixed root cause for every founder, ending in a canned
                report. Problem.jsx now hands off straight to the real, backend-driven
                diagnosis at /app/diagnosis instead. */}
            <Route path="*" element={<Navigate to="/guided/login" replace />} />
          </Route>

          {/* ── Main platform ── */}
          <Route path="/app" element={
            <ErrorBoundary label="Platform" fallbackPath="/app">
              <RequireAuth>
                <PlatformLayout />
              </RequireAuth>
            </ErrorBoundary>
          }>
            <Route index element={<Dashboard />} />
            <Route path="ally-chat" element={<AllyChat />} />
            {/* The identity phase, asked BEFORE the business diagnosis --
                /diagnosis/start 409s until it completes. Distinct from
                "founder-dna" below, which is the read-only result card:
                this one is where the founder answers. */}
            <Route path="founder-dna-journey" element={<FounderDnaChat />} />
            {/* Phase 2 of 3. Reached from the Founder DNA journey rather than
                linked directly -- see PlatformLayout, where the one "Start
                Diagnosis" entry point still points at founder-dna-journey and
                each phase passes through once complete. */}
            <Route path="current-problem" element={<CurrentProblemChat />} />
            <Route path="diagnosis" element={<DiagnosisChat />} />
            <Route path="thinking" element={<Thinking />} />
            <Route path="founder-dna" element={<FounderDNA />} />
            <Route path="vision" element={<VisionPage />} />
            <Route path="business-dna" element={<BusinessDNA />} />
            <Route path="journey" element={<JourneyPage />} />
            <Route path="achievements" element={<AchievementsPage />} />
            <Route path="goals" element={<GoalsPage />} />
            <Route path="recommendations" element={<RecommendationsPage />} />
            <Route path="frameworks" element={<FrameworksPage />} />
            <Route path="frameworks/:id" element={<FrameworkDetail />} />
            <Route path="profile" element={<FounderProfile />} />
            <Route path="plan" element={<PlanYourDay />} />
            <Route path="know-my-energy" element={<KnowMyEnergy />} />
            <Route path="next-steps" element={<NextSteps />} />
            <Route path="discovery-call" element={<DiscoveryCall />} />
            <Route path="feedback" element={<Feedback />} />
            <Route path="report" element={<Report />} />
            <Route path="billing" element={<Billing />} />
            <Route path="help" element={<HelpSupport />} />
          </Route>

          {/* ── Admin Panel (internal) ── */}
          <Route path="/admin" element={
            <ErrorBoundary label="Admin" fallbackPath="/admin">
              <AdminLayout />
            </ErrorBoundary>
          }>
            <Route index element={<AdminDashboard />} />
            <Route path="users" element={<AdminUsers />} />
            <Route path="users/:id" element={<AdminUserDetail />} />
            <Route path="usage" element={<AdminUsage />} />
            <Route path="audit" element={<AdminAuditLog />} />
            <Route path="system" element={<AdminSystem />} />
          </Route>

          {/* Unknown routes get a real 404 rather than a silent <Navigate to="/">,
              which erased the failing URL from history before anyone could read
              it and made a dead link look like a deliberate trip home. */}
          <Route path="*" element={<NotFound />} />
        </Routes>
      </Suspense>
      <Toast message={toast} />
      <CookieBanner />
    </>
  );
}
