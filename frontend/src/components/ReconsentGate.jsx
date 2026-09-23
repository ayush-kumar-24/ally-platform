import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import Modal from './Modal';
import { useApp } from '../context/AppContext';
import { acceptUpdatedPolicies, getConsents } from '../services/consents';

/**
 * Asks a founder to re-accept the Terms and Privacy Policy after they change.
 *
 * WHY THIS EXISTS. The backend has always computed `needs_reconsent` -- it
 * compares the founder's stored version against the current one and is exactly
 * how a policy update is meant to re-prompt. Nothing in the frontend read it.
 * So bumping the documents recorded the new version for NEW sign-ups and left
 * everyone else attached, in the ledger, to text that had been replaced, with
 * no way for them to move and nothing telling them it had happened.
 *
 * DISMISSIBLE, unlike DeletionPendingGate. Consent has to be freely given; a
 * dialog that locks a founder out of their own data until they agree is not a
 * request, and it would be a poor answer for a change that mostly CORRECTS
 * overstated claims in the founder's favour. So: shown on the way in, snoozed
 * for the session if they want to read first, and back next time. Their old
 * consent stays in force until they act, which is the honest position -- they
 * did agree to something, just not to this.
 *
 * Nothing about the product is gated on the answer. If that ever changes --
 * if a future revision genuinely alters what we do with their data rather
 * than how we describe it -- that is a deliberate decision to make here, not
 * something to inherit by accident from this component.
 */

/* Session-scoped on purpose. localStorage would mean "later" silently became
   "never" on that device. */
const SNOOZE_KEY = 'ally.reconsent_snoozed';

export default function ReconsentGate() {
  const { showToast } = useApp();
  const [due, setDue] = useState(false);
  const [working, setWorking] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        if (sessionStorage.getItem(SNOOZE_KEY)) return;
      } catch {
        // Private browsing can throw on sessionStorage. Losing the snooze is
        // an annoyance; failing to ask is a compliance gap, so carry on.
      }
      try {
        const status = await getConsents();
        if (cancelled) return;
        // has_consented guards the sign-up path: someone who has never
        // consented is mid-onboarding and gets the real form, not this.
        if (status?.has_consented && status?.needs_reconsent) setDue(true);
      } catch {
        // A status call that fails must never put a dialog in someone's way.
      }
    })();
    return () => { cancelled = true; };
  }, []);

  const accept = async () => {
    if (working) return;
    setWorking(true);
    try {
      await acceptUpdatedPolicies();
      setDue(false);
      showToast('Thank you — your agreement has been updated.');
    } catch (err) {
      showToast(err?.detail || "Couldn't record that just now — please try again.");
    } finally {
      setWorking(false);
    }
  };

  const later = () => {
    try {
      sessionStorage.setItem(SNOOZE_KEY, '1');
    } catch {
      // See above. Worst case they are asked again on the next page load.
    }
    setDue(false);
  };

  if (!due) return null;

  return (
    <Modal open onClose={later} title="We've updated our Terms and Privacy Policy">
      <p className="modal-sub">
        We have rewritten parts of both documents to describe what Ally actually
        does more accurately. The main changes: we no longer claim blanket
        compliance with the DPDP Act, we have corrected how we describe the
        legal basis for processing your data, we have removed security claims we
        could not evidence, and we now commit to telling you and the Data
        Protection Board about any personal data breach — with no severity
        threshold of our own.
      </p>
      <p className="modal-sub">
        Nothing about what we do with your data has changed, and your existing
        choices — including whether we may process your diagnostic answers —
        are carried across exactly as they are.
      </p>
      <p className="modal-sub">
        <Link to="/privacy" target="_blank" rel="noopener noreferrer">Read the Privacy Policy</Link>
        {' · '}
        <Link to="/terms" target="_blank" rel="noopener noreferrer">Read the Terms of Service</Link>
      </p>
      <div className="modal-actions">
        <button className="btn btn-ghost" type="button" onClick={later} disabled={working}>
          I&apos;ll read them first
        </button>
        <button className="btn btn-em" type="button" onClick={accept} disabled={working}>
          {working ? 'Saving…' : 'I agree to the updated documents'}
        </button>
      </div>
    </Modal>
  );
}
