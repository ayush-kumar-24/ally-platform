import { Routes, Route, Navigate } from 'react-router-dom';
import { useApp } from './context/AppContext';
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
import Reveal from './pages/guided/Reveal';
import RootCause from './pages/guided/RootCause';
import Conclusion from './pages/guided/Conclusion';
import GuidedReport from './pages/guided/GuidedReport';
import Recommend from './pages/guided/Recommend';
import Discovery from './pages/guided/Discovery';
import Success from './pages/guided/Success';
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
import Report from './pages/Report';
import Billing from './pages/Billing';
import HelpSupport from './pages/HelpSupport';
import Toast from './components/ui/Toast';

export default function App() {
  const { toast } = useApp();

  return (
    <>
      <Routes>
        <Route element={<LandingLayout />}>
          <Route path="/" element={<LandingPage />} />
        </Route>
        <Route path="/guided" element={<GuidedLayout />}>
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
          <Route path="reveal" element={<Reveal />} />
          <Route path="root-cause" element={<RootCause />} />
          <Route path="conclusion" element={<Conclusion />} />
          <Route path="report" element={<GuidedReport />} />
          <Route path="recommend" element={<Recommend />} />
          <Route path="discovery" element={<Discovery />} />
          <Route path="success" element={<Success />} />
        </Route>
        <Route path="/app" element={<PlatformLayout />}>
          <Route index element={<Dashboard />} />
          <Route path="ally-chat" element={<AllyChat />} />
          <Route path="diagnosis" element={<DiagnosisChat />} />
          <Route path="thinking" element={<Thinking />} />
          <Route path="founder-dna" element={<FounderDNA />} />
          <Route path="business-dna" element={<BusinessDNA />} />
          <Route path="profile" element={<FounderProfile />} />
          <Route path="plan" element={<PlanYourDay />} />
          <Route path="next-steps" element={<NextSteps />} />
          <Route path="discovery-call" element={<DiscoveryCall />} />
          <Route path="report" element={<Report />} />
          <Route path="billing" element={<Billing />} />
          <Route path="help" element={<HelpSupport />} />
        </Route>
      </Routes>
      <Toast message={toast} />
    </>
  );
}
