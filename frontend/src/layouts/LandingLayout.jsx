import { Outlet } from 'react-router-dom';

export default function LandingLayout() {
  return (
    <div className="min-h-dvh bg-forest-night text-white font-body overflow-x-hidden">
      <Outlet />
    </div>
  );
}
