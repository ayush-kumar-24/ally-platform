import { useNavigate } from 'react-router-dom';
import ReportView from '../components/ReportView';

/* Dashboard report route (/app/report). Thin host around the shared ReportView
   so it can never diverge from the guided report. */
export default function Report() {
  const navigate = useNavigate();
  return (
    <div className="fd-container">
      <ReportView onBook={() => navigate('/app/billing')} />
    </div>
  );
}
