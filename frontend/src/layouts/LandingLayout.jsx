import { Outlet } from 'react-router-dom';

export default function LandingLayout() {
  return (
    <div className="min-h-dvh bg-forest-night text-white font-body overflow-x-hidden">
      {/* The landing page had no main landmark at all, so "skip to content" and
          every screen reader's landmark menu had nothing to jump to. */}
      <main id="main-content" tabIndex={-1}>
        <Outlet />
      </main>
    </div>
  );
}
