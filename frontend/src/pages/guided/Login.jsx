import { useEffect, useRef, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useApp } from '../../context/AppContext';
import AuthTransition from '../../components/AuthTransition';
import { CURRENT_VERSIONS, flushPendingConsent, recordConsent, savePendingConsent } from '../../services/consents';
import { consumeOAuthRedirect, signInWithGoogle, signInWithLinkedIn, startDevSession } from '../../services/auth';
import { get } from '../../services/api';
import { supabaseConfigured } from '../../services/supabaseConfig';
import { firstSafe } from '../../utils/looksLikeToken';

export default function Login() {
  const navigate = useNavigate();
  const location = useLocation();
  // Where they were going before the session ran out, if anywhere.
  const returnTo = location.state?.from || '/guided/welcome';
  const { setUser } = useApp();
  const [showAuthTransition, setShowAuthTransition] = useState(false);
  const [agreeTerms, setAgreeTerms] = useState(false);
  const [agreeDiagnosis, setAgreeDiagnosis] = useState(false);
  const [validationError, setValidationError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  // Ref, not state: state updates are async, so two clicks in the same tick would
  // both see `submitting === false` and both fire. The ref flips synchronously.
  const inFlight = useRef(false);

  // Google/LinkedIn redirect the whole page away and back -- this picks the
  // session up on the return trip. No-ops (returns null fast) on every other
  // load, since consumeOAuthRedirect only finds something when the URL
  // actually carries a fresh Supabase session.
  useEffect(() => {
    if (!supabaseConfigured) return;
    (async () => {
      /* consumeOAuthRedirect POSTs /auth/session, which throws ApiError on any
         failure. With no catch that became an unhandled rejection and the
         founder — who has just come back from Google having signed in
         successfully — was dropped on this screen with no message at all,
         indistinguishable from the sign-in never having started. */
      let founder;
      try {
        founder = await consumeOAuthRedirect();
      } catch {
        setValidationError(
          "We couldn't finish signing you in. Please try again.",
        );
        return;
      }
      if (!founder) return;

      let profile = null;
      try {
        profile = await get('/profile');
      } catch {
        // Provisioning races the very first request sometimes; the rest of the
        // app re-fetches /profile on its own, so a miss here isn't fatal.
      }

      /* A returning founder who already finished onboarding must not be sent
         back through it. GuidedLayout has its own profile_completed guard,
         but it only runs once per mount -- and this component mounted BEFORE
         the token existed (that's the whole point of this effect), so by the
         time the guard could re-check, it never fires again. This is the one
         place the answer is actually knowable at the moment it matters: right
         after the session is established, with the freshly-fetched profile in
         hand. Skip the "signing you in" transition and the 14-step shell
         entirely -- there is nothing to resume into. */
      if (profile?.profile_completed) {
        navigate('/app', { replace: true });
        return;
      }

      let stored = null;
      try {
        stored = await flushPendingConsent();
      } catch {
        // Stays pending in localStorage; flushed again on the next app load.
      }

      setUser((prev) => ({
        ...prev,
        // 'google' | 'linkedin_oidc' -- whichever the founder actually used,
        // read from the backend's own response rather than assumed.
        authProvider: founder.provider,
        // firstSafe, not a plain ||: live-reproduced with a dev-mode backend,
        // founder.email can itself be a synthesized "<raw token>@ally.local"
        // placeholder for a founder who hasn't provisioned yet -- a fallback
        // chain that trusts it blindly renders a 250-character JWT as the
        // founder's name on their very first screen. See looksLikeToken.js.
        name: firstSafe([profile?.full_name, founder.email, prev?.name]),
        email: firstSafe([founder.email, prev?.email]),
        plan_type: profile?.plan_type || prev?.plan_type,
        consents: stored ? {
          termsAccepted: true,
          termsVersion: stored.terms_version,
          privacyVersion: stored.privacy_version,
          diagnosisConsent: stored.agree_diagnosis,
          consentedAt: stored.consented_at,
          consentId: stored.consent_id,
          synced: true,
        } : prev?.consents,
      }));
      setShowAuthTransition(true);
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleAuth = async (provider) => {
    if (inFlight.current) return;
    if (!agreeTerms) {
      setValidationError('Please agree to the Terms of Service and Privacy Policy to continue.');
      return;
    }
    inFlight.current = true;
    setSubmitting(true);
    setValidationError('');

    const choices = { agreeTerms: true, agreeDiagnosis };
    let stored = null;
    try {
      stored = await recordConsent(choices);
    } catch (err) {
      // A 422 means the server rejected the consent itself (bad version, terms not
      // accepted) — that is a real failure and must not be waved through.
      if (err.status === 422) {
        setValidationError(err.detail || 'We could not record your consent. Please try again.');
        inFlight.current = false;
        setSubmitting(false);
        return;
      }
      // Anything else (offline, or no session yet because sign-in is still
      // simulated) — hold the consent locally and flush it once a session exists,
      // so the user's actual choice is never silently lost.
      savePendingConsent(choices);
    }

    // Real sign-in: redirect to the provider now. The rest of this function
    // (the simulated identity below) is skipped entirely -- the mount-time
    // effect above picks the flow back up once the provider redirects here,
    // and flushes the pending consent captured just above.
    if (supabaseConfigured && (provider === 'google' || provider === 'linkedin')) {
      try {
        await (provider === 'google' ? signInWithGoogle() : signInWithLinkedIn());
      } catch {
        setValidationError(`Could not start ${provider === 'google' ? 'Google' : 'LinkedIn'} sign-in. Please try again.`);
        inFlight.current = false;
        setSubmitting(false);
      }
      return; // navigates away on success; nothing left to do
    }

    // Supabase isn't configured (local dev). Establish a real backend session
    // against the dev founder rather than inventing an identity: a fabricated
    // name is worse than none -- the founder can't tell it's fake -- and with no
    // token nothing they enter downstream can actually save.
    let devFounder = null;
    let devProfile = null;
    try {
      devFounder = await startDevSession();
      if (devFounder) devProfile = await get('/profile');
    } catch {
      // Backend down, or no dev founder configured. Fall through with no
      // identity; AppContext re-hydrates from /profile once a session exists.
    }

    /* No real provider AND no dev token (this is what production looks like
       right now, with Supabase unconfigured): there is no way to get a session
       here, full stop. The old code fell through anyway -- set a mostly-empty
       user, play the "signing you in" animation, and navigate into a guarded
       route with no token. GuidedLayout's own auth check then bounced straight
       back here, so the founder watched the animation play and landed back on
       this exact screen -- indistinguishable from nothing having happened. Say
       so instead of performing a sign-in that cannot succeed. */
    if (!devFounder) {
      setValidationError(
        'Sign-in is not available in this environment yet. Please try again shortly.',
      );
      inFlight.current = false;
      setSubmitting(false);
      return;
    }

    // firstSafe, not a plain ||: see the OAuth branch above -- the same
    // token-as-placeholder-email shape can come back here too if
    // VITE_DEV_FOUNDER_TOKEN isn't a real uuid.
    const devName = firstSafe([devProfile?.full_name]);

    setUser(prev => ({
      ...prev,
      authProvider: provider,
      name: devName,
      email: firstSafe([devProfile?.email, devFounder?.email]),
      initials: devName.split(' ').filter(Boolean).slice(0, 2)
        .map(w => w[0].toUpperCase()).join('') || '?',
      consents: {
        termsAccepted: true,
        termsVersion: stored?.terms_version ?? CURRENT_VERSIONS.terms,
        privacyVersion: stored?.privacy_version ?? CURRENT_VERSIONS.privacy,
        diagnosisConsent: stored?.agree_diagnosis ?? agreeDiagnosis,
        // Server-stamped when persisted; only falls back to client time when the
        // record is still pending sync.
        consentedAt: stored?.consented_at ?? new Date().toISOString(),
        consentId: stored?.consent_id ?? null,
        synced: stored !== null,
      }
    }));
    setSubmitting(false);
    setShowAuthTransition(true);
  };

  return (
    <section className="view j-stage active auth-active" id="v-login">
      {showAuthTransition && (
        <AuthTransition
          // RequireAuth records where the founder was heading when their
          // session ran out. Without honouring it, anyone whose token expired
          // mid-flow was dropped back at the start of onboarding with no
          // explanation and no way back to where they were.
          onNavigate={() => navigate(returnTo, { replace: true })}
          onComplete={() => setShowAuthTransition(false)}
        />
      )}
      <div className="j-inner">
        <div className="j-avatar"><img src="/ally-logo.png" alt="" /></div>
        <div className="j-eye"><span className="lv"></span> GoXL &middot; Ally</div>
        <h1 className="j-title">Meet Ally, your <em>founder DNA</em> engine.</h1>
        <p className="j-sub">In about 20 minutes, Ally learns how you lead and finds what's really holding your business back. You'll leave with a clarity report and your next move.</p>
        
        {validationError && (
          <div className="consent-error" role="alert" id="consent-error">
            {validationError}
          </div>
        )}

        <div className="consent-container">
          <label className="consent-item">
            {/* This is the gate handleAuth refuses to proceed without, but
                nothing said so programmatically — the error appeared visually
                with no link back to the field it blamed. */}
            <input
              type="checkbox"
              id="consent-terms"
              required
              aria-required="true"
              aria-invalid={validationError && !agreeTerms ? 'true' : undefined}
              aria-describedby={validationError ? 'consent-error' : undefined}
              checked={agreeTerms}
              disabled={submitting}
              onChange={(e) => {
                setAgreeTerms(e.target.checked);
                if (e.target.checked) setValidationError('');
              }}
            />
            <span className="consent-text">
              I agree to the <a href="/terms" target="_blank" rel="noopener noreferrer" onClick={(e) => e.stopPropagation()}>Terms of Service</a> and <a href="/privacy" target="_blank" rel="noopener noreferrer" onClick={(e) => e.stopPropagation()}>Privacy Policy</a> <span className="version-tag">v{CURRENT_VERSIONS.terms}</span> <span className="req">*</span>
            </span>
          </label>
          
          <label className="consent-item">
            <input 
              type="checkbox" 
              id="consent-diagnosis"
              checked={agreeDiagnosis}
              disabled={submitting}
              onChange={(e) => setAgreeDiagnosis(e.target.checked)}
            />
            <span className="consent-text">
              I consent to the collection and processing of my business's diagnostic information as described in the Privacy Policy.
            </span>
          </label>
        </div>

        <div className="j-auth">
          <button className="auth-btn" onClick={() => handleAuth('google')} type="button"
                  disabled={submitting} aria-busy={submitting}>
            <svg className="g" viewBox="0 0 48 48" aria-hidden="true">
              <path fill="#EA4335" d="M24 9.5c3.5 0 6.6 1.2 9 3.6l6.8-6.8C35.6 2.4 30.1 0 24 0 14.6 0 6.5 5.4 2.6 13.2l7.9 6.1C12.4 13.2 17.7 9.5 24 9.5z" />
              <path fill="#4285F4" d="M46.1 24.6c0-1.6-.1-3.1-.4-4.6H24v9.1h12.4c-.5 2.9-2.1 5.3-4.6 7l7.1 5.5c4.2-3.9 6.6-9.6 6.6-16.4z" />
              <path fill="#FBBC05" d="M10.5 28.3c-.5-1.4-.7-2.9-.7-4.3s.3-3 .7-4.3l-7.9-6.1C1 16.7 0 20.2 0 24s1 7.3 2.6 10.4l7.9-6.1z" />
              <path fill="#34A853" d="M24 48c6.1 0 11.3-2 15-5.5l-7.1-5.5c-2 1.4-4.6 2.2-7.9 2.2-6.3 0-11.6-3.7-13.5-9.1l-7.9 6.1C6.5 42.6 14.6 48 24 48z" />
            </svg>
            Continue with Google
          </button>
          <button className="auth-btn li" onClick={() => handleAuth('linkedin')} type="button"
                  disabled={submitting} aria-busy={submitting}>
            <svg className="g" viewBox="0 0 24 24" fill="#fff" aria-hidden="true">
              <path d="M4.98 3.5A2.5 2.5 0 1 0 5 8.5a2.5 2.5 0 0 0-.02-5zM3 9h4v12H3zM9 9h3.8v1.7h.05c.53-1 1.83-2.05 3.77-2.05 4.03 0 4.78 2.65 4.78 6.1V21H19.6v-5.3c0-1.26-.02-2.9-1.77-2.9-1.77 0-2.04 1.38-2.04 2.8V21H9z" />
            </svg>
            Continue with LinkedIn
          </button>
        </div>
        <p className="j-fine">
          Private &amp; encrypted &middot; we never share your business.{' '}
          {!supabaseConfigured && (
            <span style={{ opacity: 0.7 }}>(Demo — simulated login, no account created)</span>
          )}
        </p>
      </div>
    </section>
  );
}
