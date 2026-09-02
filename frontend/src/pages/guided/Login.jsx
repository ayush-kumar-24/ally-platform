/**
 * Login — email as the identifier, an emailed OTP to prove it, a password for
 * next time.
 *
 * Three steps, all on this one screen (nothing redirects away and back, so
 * unlike the OAuth flow this replaces there is no session to pick up on mount):
 *
 *   'password'  returning founder types email + password
 *   'email'     first time here, or forgot the password: type email, get a code
 *   'code'      type the code and choose a password -> signed in
 *
 * The 'email' -> 'code' path is the ONLY one that can create an account, so the
 * consent gate lives there. A founder signing in with a password consented when
 * they signed up.
 */

import { useEffect, useRef, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useApp } from '../../context/AppContext';
import AuthTransition from '../../components/AuthTransition';
import { CURRENT_VERSIONS, flushPendingConsent, recordConsent, savePendingConsent } from '../../services/consents';
import { sendEmailOtp, signInWithPassword, startDevSession, verifyOtpAndSetPassword } from '../../services/auth';
import { get } from '../../services/api';
import { DEV_MOCK_CODE, devMockAuth, supabaseConfigured, WAITLIST_URL } from '../../services/supabaseConfig';
import { firstSafe } from '../../utils/looksLikeToken';

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

/** Keep in step with the minimum length configured in the Supabase dashboard.
 *  Checking here too means a too-short password is caught before the round trip,
 *  with a message that names the actual requirement. */
const MIN_PASSWORD_LENGTH = 8;

/** Must be >= the "Minimum interval between emails" configured in Supabase's SMTP
 *  settings (60s), or the Resend button unlocks while Supabase is still refusing
 *  to send -- the founder presses a button we just told them was ready and gets
 *  an error. This timer starts when the send RESPONDS, i.e. slightly after
 *  Supabase's own window opened, so equal values are safe with room to spare. */
const RESEND_COOLDOWN_SECONDS = 60;

/** Supabase's OTP length is a project setting, not a constant -- this project
 *  issues 8 digits, the Supabase default is 6, and it can be raised to 10.
 *  Hard-coding 6 here (as this did) capped the input via maxLength and silently
 *  truncated an 8-digit code to its first 6, so verification failed for every
 *  founder with no visible reason. Accept the whole configurable range instead,
 *  so changing that setting in the dashboard can never lock anyone out. */
const OTP_MIN_LENGTH = 6;
const OTP_MAX_LENGTH = 10;
/** Display only -- this project's actual configured length (see the note
 *  above), used for the confirmation copy and the input's placeholder. Kept
 *  separate from OTP_MIN_LENGTH/MAX_LENGTH on purpose: those stay a wide,
 *  permissive validation range so a dashboard change never locks anyone out,
 *  while this is just what a founder is told to expect right now. Live-
 *  reproduced: the copy still said "6-digit" and showed a 6-zero placeholder
 *  ("000000") despite the project actually issuing 8-digit codes -- correct
 *  codes looked one digit short of matching what was shown on screen. */
const OTP_DISPLAY_LENGTH = 8;

export default function Login() {
  const navigate = useNavigate();
  const location = useLocation();
  // Where they were going before the session ran out, if anywhere.
  const returnTo = location.state?.from || '/guided/welcome';
  const { setUser } = useApp();

  const [step, setStep] = useState('password');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [code, setCode] = useState('');
  const [fullName, setFullName] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');

  const [showAuthTransition, setShowAuthTransition] = useState(false);
  const [agreeTerms, setAgreeTerms] = useState(false);
  const [agreeDiagnosis, setAgreeDiagnosis] = useState(false);
  const [validationError, setValidationError] = useState('');
  const [notice, setNotice] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [cooldown, setCooldown] = useState(0);
  // Ref, not state: state updates are async, so two submits in the same tick
  // would both see `submitting === false` and both fire. The ref flips
  // synchronously.
  const inFlight = useRef(false);

  useEffect(() => {
    if (cooldown <= 0) return undefined;
    const timer = setTimeout(() => setCooldown((s) => s - 1), 1000);
    return () => clearTimeout(timer);
  }, [cooldown]);

  /* Arriving from the approval email: its link is /guided/login#email=<addr>.
     A fragment, not a query string -- it never reaches any server, so the
     address is in no access log along the way. Read once, then removed from
     the address bar so it does not linger in history or get re-applied on a
     refresh. The founder still presses "Send me a code" themselves: nothing
     in a URL may trigger an email, or a crafted link could spam any inbox. */
  useEffect(() => {
    const applyEmailFromHash = () => {
      const match = /(?:^#|&)email=([^&]+)/.exec(window.location.hash);
      if (!match) return;
      let candidate = '';
      try { candidate = decodeURIComponent(match[1]).trim(); } catch { /* not ours */ }
      window.history.replaceState(null, '', window.location.pathname + window.location.search);
      if (!EMAIL_RE.test(candidate)) return;
      setEmail(candidate);
      setStep('email');
    };
    applyEmailFromHash();
    // Also when the link is followed while this page is already open: a
    // fragment-only navigation does not remount the component.
    window.addEventListener('hashchange', applyEmailFromHash);
    return () => window.removeEventListener('hashchange', applyEmailFromHash);
  }, []);

  const release = () => {
    inFlight.current = false;
    setSubmitting(false);
  };

  const goToStep = (next) => {
    setStep(next);
    setValidationError('');
    setNotice('');
  };

  /**
   * Everything that happens once a backend session exists, whichever door they
   * came through: rehydrate the profile, flush any consent captured before the
   * session existed, then play the transition into the app.
   */
  const finishSignIn = async (founder) => {
    let profile = null;
    try {
      profile = await get('/profile');
    } catch {
      // Provisioning races the very first request sometimes; the rest of the
      // app re-fetches /profile on its own, so a miss here isn't fatal.
    }
    /* A returning founder who already finished onboarding must not be sent back
       through it. GuidedLayout has its own profile_completed guard, but it only
       runs once per mount -- and this component mounted BEFORE the token
       existed, so by the time the guard could re-check, it never fires again.
       This is the one place the answer is knowable at the moment it matters:
       right after the session is established, with the freshly-fetched profile
       in hand. Skip the "signing you in" transition and the 14-step shell --
       there is nothing to resume into. (Carried over from origin/main's OAuth
       mount effect, which this email/OTP flow replaced.) */
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

    /* firstSafe, not a plain ||: founder.email can itself be a synthesized
       "<raw token>@ally.local" placeholder for a founder who hasn't provisioned
       yet, and a fallback chain that trusts it blindly renders a 250-character
       JWT as the founder's name on their very first screen. See
       looksLikeToken.js. */
    const name = firstSafe([profile?.full_name, founder.email]);
    setUser((prev) => ({
      ...prev,
      authProvider: founder.provider,
      name: name || prev?.name,
      email: firstSafe([founder.email, prev?.email]),
      initials: name.split(' ').filter(Boolean).slice(0, 2)
        .map((w) => w[0].toUpperCase()).join('') || '?',
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
    setSubmitting(false);
    setShowAuthTransition(true);
  };

  // ── Returning founder: email + password ───────────────────────────────────

  const handlePasswordSignIn = async (e) => {
    e.preventDefault();
    if (inFlight.current) return;
    if (!email.trim() || !password) {
      setValidationError('Please enter your email and password.');
      return;
    }
    inFlight.current = true;
    setSubmitting(true);
    setValidationError('');

    try {
      const founder = await signInWithPassword(email, password);
      await finishSignIn(founder);
      inFlight.current = false;
    } catch (err) {
      setValidationError(err.message || 'We could not sign you in. Please try again.');
      release();
    }
  };

  // ── First time / forgot password: send the code ───────────────────────────

  const sendCode = async ({ isResend }) => {
    try {
      await sendEmailOtp(email);
      setCooldown(RESEND_COOLDOWN_SECONDS);
      setNotice(devMockAuth
        ? `Dev mock: no email is sent. The code is ${DEV_MOCK_CODE}.`
        : `We sent a ${OTP_DISPLAY_LENGTH}-digit code to ${email.trim()}. It expires in a few minutes.`);
      if (!isResend) setStep('code');
      return true;
    } catch (err) {
      setValidationError(err.message || "We couldn't send that code. Please try again.");
      return false;
    }
  };

  const handleSendCode = async (e) => {
    e.preventDefault();
    if (inFlight.current) return;
    if (!email.trim()) {
      setValidationError('Please enter your email address.');
      return;
    }
    if (!agreeTerms) {
      setValidationError('Please agree to the Terms of Service and Privacy Policy to continue.');
      return;
    }
    inFlight.current = true;
    setSubmitting(true);
    setValidationError('');
    setNotice('');

    /* Capture consent before the account exists. recordConsent needs a session,
       which there isn't one of yet, so in practice this stores locally and
       finishSignIn flushes it the moment a session appears. A 422 is different:
       the server rejected the consent itself (bad version, terms not accepted),
       and that must not be waved through. */
    const choices = { agreeTerms: true, agreeDiagnosis };
    try {
      await recordConsent(choices);
    } catch (err) {
      if (err.status === 422) {
        setValidationError(err.detail || 'We could not record your consent. Please try again.');
        release();
        return;
      }
      savePendingConsent(choices);
    }

    await sendCode({ isResend: false });
    release();
  };

  const handleResend = async () => {
    if (inFlight.current || cooldown > 0) return;
    inFlight.current = true;
    setSubmitting(true);
    setValidationError('');
    await sendCode({ isResend: true });
    release();
  };

  // ── Verify the code and choose a password ─────────────────────────────────

  const handleVerify = async (e) => {
    e.preventDefault();
    if (inFlight.current) return;
    if (code.trim().length < OTP_MIN_LENGTH) {
      setValidationError('Please enter the full code from your email.');
      return;
    }
    if (!fullName.trim()) {
      setValidationError('Please tell us your name.');
      return;
    }
    if (newPassword.length < MIN_PASSWORD_LENGTH) {
      setValidationError(`Please choose a password of at least ${MIN_PASSWORD_LENGTH} characters.`);
      return;
    }
    if (newPassword !== confirmPassword) {
      setValidationError('Those two passwords do not match.');
      return;
    }
    inFlight.current = true;
    setSubmitting(true);
    setValidationError('');
    setNotice('');

    try {
      const founder = await verifyOtpAndSetPassword(email, code, newPassword, fullName);
      await finishSignIn(founder);
      inFlight.current = false;
    } catch (err) {
      setValidationError(err.message || 'We could not verify that code. Please try again.');
      release();
    }
  };

  // ── Local development, with no Supabase configured ────────────────────────

  const handleDevSignIn = async () => {
    if (inFlight.current) return;
    inFlight.current = true;
    setSubmitting(true);
    setValidationError('');

    let devFounder = null;
    try {
      devFounder = await startDevSession();
    } catch {
      // Backend down, or no dev founder configured -- handled just below.
    }

    /* No real provider AND no dev token (this is what production looks like
       with Supabase unconfigured): there is no way to get a session here, full
       stop. Falling through anyway would play the "signing you in" animation
       and navigate into a guarded route with no token, which GuidedLayout
       bounces straight back to this screen -- indistinguishable from nothing
       having happened. Say so instead of performing a sign-in that cannot
       succeed. */
    if (!devFounder) {
      setValidationError('Sign-in is not available in this environment yet. Please try again shortly.');
      release();
      return;
    }

    await finishSignIn(devFounder);
    inFlight.current = false;
  };

  // ── Render ────────────────────────────────────────────────────────────────

  const consentGate = (
    <div className="consent-container">
      <label className="consent-item">
        {/* This is the gate handleSendCode refuses to proceed without, but
            nothing said so programmatically — the error appeared visually with
            no link back to the field it blamed. */}
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
  );

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
        {notice && !validationError && (
          <div className="auth-notice" role="status">{notice}</div>
        )}

        {!supabaseConfigured ? (
          <div className="auth-form">
            <button className="auth-btn auth-submit" type="button" onClick={handleDevSignIn}
                    disabled={submitting} aria-busy={submitting}>
              Continue (local development)
            </button>
          </div>
        ) : step === 'password' ? (
          <form className="auth-form" onSubmit={handlePasswordSignIn} noValidate>
            <label className="auth-field">
              <span className="auth-label">Email</span>
              <input className="auth-input" type="email" name="email" autoComplete="username"
                     inputMode="email" placeholder="you@company.com" value={email}
                     disabled={submitting}
                     onChange={(e) => { setEmail(e.target.value); setValidationError(''); }} />
            </label>
            <label className="auth-field">
              <span className="auth-label">Password</span>
              <input className="auth-input" type="password" name="password"
                     autoComplete="current-password" placeholder="Your password" value={password}
                     disabled={submitting}
                     onChange={(e) => { setPassword(e.target.value); setValidationError(''); }} />
            </label>
            <button className="auth-btn auth-submit" type="submit"
                    disabled={submitting} aria-busy={submitting}>
              Sign in
            </button>
            <p className="auth-alt">
              First time here, or forgotten your password?{' '}
              <button type="button" className="auth-link-btn" disabled={submitting}
                      onClick={() => goToStep('email')}>
                Email me a code
              </button>
            </p>
            <p className="auth-alt">
              Don&rsquo;t have access yet?{' '}
              <a className="auth-link-btn" href={WAITLIST_URL}>Join the waitlist</a>
            </p>
          </form>
        ) : step === 'email' ? (
          <form className="auth-form" onSubmit={handleSendCode} noValidate>
            <label className="auth-field">
              <span className="auth-label">Email</span>
              <input className="auth-input" type="email" name="email" autoComplete="username"
                     inputMode="email" placeholder="you@company.com" value={email} autoFocus
                     disabled={submitting}
                     onChange={(e) => { setEmail(e.target.value); setValidationError(''); }} />
            </label>

            {consentGate}

            <button className="auth-btn auth-submit" type="submit"
                    disabled={submitting} aria-busy={submitting}>
              Send me a code
            </button>
            <p className="auth-alt">
              Already have a password?{' '}
              <button type="button" className="auth-link-btn" disabled={submitting}
                      onClick={() => goToStep('password')}>
                Sign in instead
              </button>
            </p>
            <p className="auth-alt">
              Don&rsquo;t have access yet?{' '}
              <a className="auth-link-btn" href={WAITLIST_URL}>Join the waitlist</a>
            </p>
          </form>
        ) : (
          <form className="auth-form" onSubmit={handleVerify} noValidate>
            <label className="auth-field">
              <span className="auth-label">Code from your email</span>
              <input className="auth-input auth-code" type="text" name="otp"
                     autoComplete="one-time-code" inputMode="numeric" maxLength={OTP_MAX_LENGTH}
                     placeholder={'0'.repeat(OTP_DISPLAY_LENGTH)} value={code} autoFocus disabled={submitting}
                     onChange={(e) => {
                       setCode(e.target.value.replace(/\D/g, '').slice(0, OTP_MAX_LENGTH));
                       setValidationError('');
                     }} />
            </label>
            {/* Google used to supply this. Nothing else in onboarding asks for
                it, and provisioning.py names the founder row from it — without
                this field every new founder is provisioned, and greeted, as the
                local part of their email address. */}
            <label className="auth-field">
              <span className="auth-label">Your name</span>
              <input className="auth-input" type="text" name="name" autoComplete="name"
                     placeholder="Priya Sharma" value={fullName} disabled={submitting}
                     onChange={(e) => { setFullName(e.target.value); setValidationError(''); }} />
            </label>
            <label className="auth-field">
              <span className="auth-label">Choose a password</span>
              <input className="auth-input" type="password" name="new-password"
                     autoComplete="new-password" placeholder={`At least ${MIN_PASSWORD_LENGTH} characters`}
                     value={newPassword} disabled={submitting}
                     onChange={(e) => { setNewPassword(e.target.value); setValidationError(''); }} />
            </label>
            <label className="auth-field">
              <span className="auth-label">Confirm password</span>
              <input className="auth-input" type="password" name="confirm-password"
                     autoComplete="new-password" placeholder="Type it again"
                     value={confirmPassword} disabled={submitting}
                     onChange={(e) => { setConfirmPassword(e.target.value); setValidationError(''); }} />
            </label>
            <button className="auth-btn auth-submit" type="submit"
                    disabled={submitting} aria-busy={submitting}>
              Verify &amp; continue
            </button>
            <p className="auth-alt">
              {cooldown > 0 ? (
                <span className="auth-resend-wait">You can request a new code in {cooldown}s</span>
              ) : (
                <button type="button" className="auth-link-btn" disabled={submitting}
                        onClick={handleResend}>
                  Send a new code
                </button>
              )}
              {' · '}
              <button type="button" className="auth-link-btn" disabled={submitting}
                      onClick={() => goToStep('email')}>
                Use a different email
              </button>
            </p>
          </form>
        )}

        <p className="j-fine">
          Private &amp; encrypted &middot; we never share your business.{' '}
          {!supabaseConfigured && (
            <span style={{ opacity: 0.7 }}>(Demo — Supabase not configured)</span>
          )}
          {devMockAuth && (
            <span style={{ opacity: 0.7 }}>(Dev mock — the code is {DEV_MOCK_CODE})</span>
          )}
        </p>
      </div>
    </section>
  );
}
