import { useCallback, useEffect, useRef } from 'react';

/**
 * A modal dialog.
 *
 * There was no reusable dialog in this codebase -- ProductTour hand-rolled its
 * own overlay and nothing else had one. This is that shell, with the parts that
 * are easy to leave out and hard to notice missing: Escape closes it, focus
 * moves into it on open and returns to wherever it came from on close, Tab is
 * trapped inside it, and the page behind cannot be scrolled while it is up.
 *
 * Props:
 *   open, onClose, title, children
 *   dismissible  false for a dialog the founder must answer or explicitly skip
 */
export default function Modal({ open, onClose, title, children, dismissible = true }) {
  const panelRef = useRef(null);
  const returnFocusTo = useRef(null);

  const close = useCallback(() => {
    if (dismissible) onClose?.();
  }, [dismissible, onClose]);

  // Remember what was focused before we stole it, so it can be given back.
  useEffect(() => {
    if (!open) return undefined;
    returnFocusTo.current = document.activeElement;
    const panel = panelRef.current;
    const first = panel?.querySelector(
      'button, [href], input, textarea, select, [tabindex]:not([tabindex="-1"])',
    );
    (first || panel)?.focus();
    return () => {
      const target = returnFocusTo.current;
      if (target && typeof target.focus === 'function') target.focus();
    };
  }, [open]);

  // The page behind a modal must not scroll -- otherwise the background moves
  // under the dialog on a trackpad and it reads as broken.
  useEffect(() => {
    if (!open) return undefined;
    const previous = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => { document.body.style.overflow = previous; };
  }, [open]);

  useEffect(() => {
    if (!open) return undefined;
    const onKeyDown = (e) => {
      if (e.key === 'Escape') { e.stopPropagation(); close(); return; }
      if (e.key !== 'Tab') return;

      const focusable = panelRef.current?.querySelectorAll(
        'button:not([disabled]), [href], input:not([disabled]), textarea:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])',
      );
      if (!focusable?.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      // Without this, Tab walks out of the dialog and into the page behind it,
      // which is still there and still focusable.
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault(); last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault(); first.focus();
      }
    };
    document.addEventListener('keydown', onKeyDown, true);
    return () => document.removeEventListener('keydown', onKeyDown, true);
  }, [open, close]);

  if (!open) return null;

  return (
    <div className="modal-overlay" onMouseDown={(e) => { if (e.target === e.currentTarget) close(); }}>
      <div
        className="modal-panel"
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        tabIndex={-1}
      >
        <div className="modal-head">
          <h2 className="modal-title">{title}</h2>
          {dismissible && (
            <button className="modal-x" type="button" aria-label="Close" onClick={close}>
              <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M18 6 6 18M6 6l12 12" /></svg>
            </button>
          )}
        </div>
        {children}
      </div>
    </div>
  );
}
