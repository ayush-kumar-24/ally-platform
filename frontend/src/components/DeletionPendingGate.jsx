import { useEffect, useState } from 'react';
import Modal from './Modal';
import { useApp } from '../context/AppContext';
import { cancelAccountDeletion, getPrivacyStatus } from '../services/privacy';
import { logout } from '../services/auth';

/**
 * Blocks the app when the founder has a scheduled account deletion pending.
 *
 * Why this exists: requesting deletion sets founders.deletion_scheduled_at, and
 * PrivacyService.may_process() gates every AI feature on that flag. Before this
 * component, a founder who clicked "Delete my account" -- including by accident,
 * which is exactly how it happened in testing -- got a bare 403 on every chat
 * message and diagnosis, with nothing in the UI explaining why. The app simply
 * stopped working for 30 days, and only an admin could undo it.
 *
 * Mounted once in PlatformLayout rather than per-feature: the deletion blocks
 * everything, so the founder should meet this on the way in, not by discovering
 * a silent failure somewhere deep in the product.
 *
 * Continuing to use Ally cancels the deletion -- but only on an explicit choice
 * here, never silently. Someone who genuinely wants to leave must be able to
 * close the door and walk away, which is what "Sign out" does.
 */
export default function DeletionPendingGate() {
  const { showToast } = useApp();
  const [pending, setPending] = useState(false);
  const [scheduledAt, setScheduledAt] = useState(null);
  const [working, setWorking] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const status = await getPrivacyStatus();
        if (cancelled) return;
        const state = status?.state;
        if (state?.deletion_pending) {
          setPending(true);
          setScheduledAt(state.deletion_scheduled_at || null);
        }
      } catch {
        // Never let a status failure lock someone out of their own account:
        // the backend gate is the real enforcement, this is only the explainer.
      }
    })();
    return () => { cancelled = true; };
  }, []);

  const keepAccount = async () => {
    if (working) return;
    setWorking(true);
    try {
      await cancelAccountDeletion();
      setPending(false);
      showToast('Welcome back — your account deletion has been cancelled.');
    } catch (err) {
      showToast(err?.detail || "Couldn't cancel that just now — please try again.");
    } finally {
      setWorking(false);
    }
  };

  const leave = async () => {
    if (working) return;
    setWorking(true);
    try {
      await logout();
    } finally {
      window.location.href = '/guided/login';
    }
  };

  if (!pending) return null;

  const when = scheduledAt
    ? new Date(scheduledAt).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })
    : null;

  return (
    // dismissible={false}: there is no "later" for this. Every AI feature is
    // already blocked server-side, so letting them past without choosing would
    // just return them to the silent-failure state this exists to end.
    <Modal open onClose={() => {}} title="Your account is scheduled for deletion" dismissible={false}>
      <p className="modal-sub">
        You asked us to delete your account{when ? `, and it is scheduled for ${when}` : ''}.
        Until then Ally has paused — no chat, no diagnosis, no new insights.
      </p>
      <p className="modal-sub">
        If that was a mistake, or you have changed your mind, continue and we
        will cancel the deletion. Nothing has been erased yet, so everything is
        still exactly where you left it.
      </p>
      <div className="modal-actions">
        <button className="btn btn-ghost" type="button" onClick={leave} disabled={working}>
          Keep deletion &amp; sign out
        </button>
        <button className="btn btn-em" type="button" onClick={keepAccount} disabled={working}>
          {working ? 'Working…' : 'Cancel deletion & continue'}
        </button>
      </div>
    </Modal>
  );
}
