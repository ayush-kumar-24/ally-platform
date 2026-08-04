import { useEffect, useState } from 'react';
import Modal from './Modal';
import StarRating from './StarRating';
import { useApp } from '../context/AppContext';
import { alreadyAnswered, listFeedback, submitFeedback } from '../services/feedback';

/**
 * Asks the founder to rate something, once.
 *
 * Mounted at the three moments worth asking at. Before showing anything it
 * checks whether this founder has already answered this exact prompt, so
 * reopening a report does not re-ask about it -- a prompt that reappears is one
 * people learn to dismiss without reading.
 *
 * Props:
 *   type       one of FEEDBACK.*
 *   title      the question, in words
 *   sessionId  / reportId   what is being rated
 *   when       gate the prompt on something being ready (defaults to true)
 */
export default function FeedbackPrompt({
  type, title, subtitle, sessionId, reportId, when = true, onResolved, dedupe = true,
}) {
  const { showToast } = useApp();
  const [open, setOpen] = useState(false);
  const [rating, setRating] = useState(0);
  const [comment, setComment] = useState('');
  const [saving, setSaving] = useState(false);

  const target = { sessionId, reportId };
  const targetKey = `${type}:${sessionId ?? ''}:${reportId ?? ''}`;

  /* `onResolved` fires on every terminal outcome -- sent, skipped, already
     answered, or nothing to ask about. Callers that pause a navigation for this
     prompt need to be released in all four cases, not just the happy one. */
  const resolve = () => { setOpen(false); onResolved?.(); };

  useEffect(() => {
    if (!when) return undefined;
    // Both types need something to attach to; asking before we have it would
    // produce a rating we cannot trace back to anything.
    const missingTarget =
      (type === 'report_rating' && reportId == null) ||
      (type === 'diagnosis_rating' && sessionId == null);
    if (missingTarget) { onResolved?.(); return undefined; }

    // Feedback the founder asked to give is never "already answered" -- that
    // check exists to stop us interrupting, not to stop them talking.
    if (!dedupe) { setOpen(true); return undefined; }

    let cancelled = false;
    listFeedback().then((items) => {
      if (cancelled) return;
      if (alreadyAnswered(items, type, target)) onResolved?.();
      else setOpen(true);
    });
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [when, targetKey]);

  const send = async () => {
    if (!rating || saving) return;
    setSaving(true);
    try {
      await submitFeedback({ type, rating, comment, sessionId, reportId });
      resolve();
      showToast('Thank you — that helps.');
    } catch {
      // Their words are not worth losing to a failed request; keep the dialog
      // open with everything still typed so they can try again.
      showToast("Couldn't send that just now — your note is still here.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal open={open} onClose={resolve} title={title}>
      {subtitle && <p className="modal-sub">{subtitle}</p>}

      <StarRating value={rating} onChange={setRating} disabled={saving} />

      <label className="sr-only" htmlFor="fb-comment">Anything you want to add</label>
      <textarea
        id="fb-comment"
        className="modal-textarea"
        rows={3}
        placeholder="Anything you'd like to add? (optional)"
        value={comment}
        disabled={saving}
        onChange={(e) => setComment(e.target.value)}
      />

      <div className="modal-actions">
        <button className="btn btn-ghost" type="button" onClick={resolve} disabled={saving}>
          Not now
        </button>
        <button className="btn btn-em" type="button" onClick={send} disabled={!rating || saving}>
          {saving ? 'Sending…' : 'Send feedback'}
        </button>
      </div>
    </Modal>
  );
}
