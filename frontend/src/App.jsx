import { useEffect, useState } from 'react';
import { Routes, Route, Navigate, useNavigate } from 'react-router-dom';
import { useApp } from './context/AppContext';
import { clearTokens, onAuthFailure } from './services/api';
import ErrorBoundary from './components/ErrorBoundary';
import RequireAuth from './components/RequireAuth';
import SplashScreen from './components/SplashScreen';
import PlatformLayout from './layouts/PlatformLayout';
import GuidedLayout from './layouts/GuidedLayout';
import LandingLayout from './layouts/LandingLayout';
import LandingPage from './pages/LandingPage';
import Login from './pages/guided/Login';
import Resume from './pages/guided/Resume';
import Expectation from './pages/guided/Expectation';
import Welcome from './pages/guided/Welcome';
import AllyIntro from './pages/guided/AllyIntro';
import ProfileBuild from './pages/guided/ProfileBuild';
import Tour from './pages/guided/Tour';
import Summary from './pages/guided/Summary';
import Validate from './pages/guided/Validate';
import Problem from './pages/guided/Problem';
import Dashboard from './pages/Dashboard';
import AllyChat from './pages/AllyChat';
import DiagnosisChat from './pages/DiagnosisChat';
import Thinking from './pages/Thinking';
import FounderProfile from './pages/FounderProfile';
import FounderDNA from './pages/FounderDNA';
import BusinessDNA from './pages/BusinessDNA';
import NextSteps from './pages/NextSteps';
import DiscoveryCall from './pages/DiscoveryCall';
import PlanYourDay from './pages/PlanYourDay';
import KnowMyEnergy from './pages/KnowMyEnergy';
import Report from './pages/Report';
import Billing from './pages/Billing';
import HelpSupport from './pages/HelpSupport';
import TermsOfService from './pages/TermsOfService';
import PrivacyPolicy from './pages/PrivacyPolicy';
import Toast from './components/ui/Toast';
import CookieBanner from './components/CookieBanner';
// Admin Panel — internal only. Access is decided by the backend (/admin/me);
// AdminLayout renders an access error for anyone the server does not recognise.
import AdminLayout from './pages/admin/AdminLayout';
import AdminDashboard from './pages/admin/AdminDashboard';
import AdminUsers from './pages/admin/AdminUsers';
import AdminUserDetail from './pages/admin/AdminUserDetail';
import AdminAuditLog from './pages/admin/AdminAuditLog';
import AdminSystem from './pages/admin/AdminSystem';
import AdminUsage from './pages/admin/AdminUsage';

// Show splash only once per session (won't replay on route changes)
const splashShown = sessionStorage.getItem('splashShown') === 'true';

export default function App() {
  const { toast } = useApp();
  const [showSplash, setShowSplash] = useState(!splashShown);
  const navigate = useNavigate();

  // A session that can't be recovered (no refresh token, or the server rejects
  // it) used to fail every request silently on whatever page the founder was
  // on -- each page showing its own generic "couldn't reach the server"
  // message, which reads as a network problem rather than "please sign in
  // again." This sends them to login instead, which is what actually fixes it.
  useEffect(() => {
    onAuthFailure(() => {
      clearTokens();
      localStorage.removeItem('ally_founder');
      navigate('/guided/login', { replace: true });
    });
  }, [navigate]);

  const handleSplashDone = () => {
    sessionStorage.setItem('splashShown', 'true');
    setShowSplash(false);
  };

  return (
    <>
      {showSplash && <SplashScreen onDone={handleSplashDone} />}
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
          <Route path="diagnosis" element={<DiagnosisChat />} />
          <Route path="thinking" element={<Thinking />} />
          <Route path="founder-dna" element={<FounderDNA />} />
          <Route path="business-dna" element={<BusinessDNA />} />
          <Route path="profile" element={<FounderProfile />} />
          <Route path="plan" element={<PlanYourDay />} />
          <Route path="know-my-energy" element={<KnowMyEnergy />} />
          <Route path="next-steps" element={<NextSteps />} />
          <Route path="discovery-call" element={<DiscoveryCall />} />
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

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
      <Toast message={toast} />
      <CookieBanner />
    </>
  );
}
