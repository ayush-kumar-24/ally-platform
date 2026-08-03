/**
 * Shared primitives for the admin pages: the loading / error / empty states and the
 * confirmation dialog. Kept in one file so every admin screen handles these the
 * same way instead of each inventing its own spinner and error copy.
 */

import { useEffect, useRef, useState } from 'react';

export function Loading({ label = 'Loading…' }) {
  return (
    <div className="adm-state" role="status" aria-live="polite">
      <span className="adm-spinner" aria-hidden="true" />
      {label}
    </div>
  );
}

export function ErrorState({ error, onRetry }) {
  const message =
    error?.detail || error?.message || 'Something went wrong. Please try again.';
  const forbidden = error?.status === 403;
  return (
    <div className="adm-state adm-state--error" role="alert">
      <strong>{forbidden ? 'Not permitted' : 'Could not load'}</strong>
      <span>{forbidden ? 'Your role does not allow this.' : message}</span>
      {onRetry && !forbidden && (
        <button className="adm-btn" onClick={onRetry} type="button">Retry</button>
      )}
    </div>
  );
}

export function EmptyState({ title = 'Nothing here', hint }) {
  return (
    <div className="adm-state adm-state--empty">
      <strong>{title}</strong>
      {hint && <span>{hint}</span>}
    </div>
  );
}

/**
 * Confirmation dialog. `danger` turns the confirm button red for destructive acts.
 * `busy` disables both buttons while the action is in flight so the dialog cannot
 * be dismissed or re-fired mid-request.
 */
export function ConfirmDialog({ open, title, body, confirmLabel = 'Confirm',
                                danger = false, busy = false, onConfirm, onCancel }) {
  const confirmRef = useRef(null);

  useEffect(() => {
    if (open) confirmRef.current?.focus();
  }, [open]);

  useEffect(() => {
    if (!open) return undefined;
    const onKey = (e) => { if (e.key === 'Escape' && !busy) onCancel?.(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, busy, onCancel]);

  if (!open) return null;
  return (
    <div className="adm-overlay" onClick={() => !busy && onCancel?.()}>
      <div className="adm-modal" role="dialog" aria-modal="true" aria-label={title}
           onClick={(e) => e.stopPropagation()}>
        <h3>{title}</h3>
        <div className="adm-modal-body">{body}</div>
        <div className="adm-modal-actions">
          <button className="adm-btn" onClick={onCancel} disabled={busy} type="button">
            Cancel
          </button>
          <button
            ref={confirmRef}
            className={`adm-btn ${danger ? 'adm-btn--danger' : 'adm-btn--primary'}`}
            onClick={onConfirm}
            disabled={busy}
            type="button"
          >
            {busy ? 'Working…' : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}

/** Small inline toast for action results. */
export function useFlash(timeout = 4000) {
  const [flash, setFlash] = useState(null);
  useEffect(() => {
    if (!flash) return undefined;
    const t = setTimeout(() => setFlash(null), timeout);
    return () => clearTimeout(t);
  }, [flash, timeout]);
  return [flash, setFlash];
}

export function Flash({ flash }) {
  if (!flash) return null;
  return (
    <div className={`adm-flash ${flash.error ? 'adm-flash--error' : ''}`} role="status">
      {flash.message}
    </div>
  );
}

export function Pagination({ page, pages, total, onChange, busy }) {
  if (!total) return null;
  return (
    <div className="adm-pagination">
      <span className="adm-muted">
        Page {page} of {pages || 1} · {total} {total === 1 ? 'user' : 'users'}
      </span>
      <div className="adm-pagination-btns">
        <button className="adm-btn" type="button" disabled={busy || page <= 1}
                onClick={() => onChange(page - 1)}>Previous</button>
        <button className="adm-btn" type="button" disabled={busy || page >= (pages || 1)}
                onClick={() => onChange(page + 1)}>Next</button>
      </div>
    </div>
  );
}
