import { Link, useLocation } from 'react-router-dom';

/**
 * 404.
 *
 * Unknown routes used to `<Navigate to="/" replace />`, which silently teleported
 * the visitor to the landing page: a mistyped or dead link was indistinguishable
 * from having clicked "home" on purpose, and the URL that failed was erased from
 * history before anyone could read it. This says what happened and offers the two
 * routes that are always valid, signed in or not.
 */
export default function NotFound() {
  const { pathname } = useLocation();

  return (
    <main
      id="main-content"
      tabIndex={-1}
      className="min-h-dvh bg-forest-night text-on-dark font-body flex items-center justify-center px-6 py-16"
    >
      <div className="w-full max-w-lg text-center">
        <p className="font-display text-7xl font-bold tracking-tight text-emerald-bright/90">404</p>

        <h1 className="mt-4 font-display text-2xl font-bold tracking-tight text-on-dark">
          We couldn&apos;t find that page
        </h1>

        <p className="mt-3 text-[0.95rem] leading-relaxed text-on-dark-muted">
          Nothing lives at{' '}
          <code className="rounded bg-white/8 px-1.5 py-0.5 text-[0.85em] break-all text-on-dark">
            {pathname}
          </code>
          . It may have moved, or the link that brought you here may be out of date.
        </p>

        <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
          <Link
            to="/"
            className="rounded-[10px] bg-linear-to-br from-emerald to-emerald-bright px-6 py-2.5 text-sm font-bold text-forest-night transition-opacity hover:opacity-90"
          >
            Back to home
          </Link>
          <Link
            to="/app"
            className="rounded-[10px] border border-line-2 bg-white/6 px-6 py-2.5 text-sm font-semibold text-on-dark transition-colors hover:bg-white/10"
          >
            Go to my dashboard
          </Link>
        </div>

        <p className="mt-8 text-[0.8rem] text-on-dark-dim">
          Still stuck?{' '}
          <a className="text-emerald-bright underline underline-offset-2" href="mailto:info@goxl.in">
            info@goxl.in
          </a>
        </p>
      </div>
    </main>
  );
}
