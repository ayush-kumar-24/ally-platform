import { useState, useEffect, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useApp } from '../context/AppContext';
import { get, post } from '../services/api';
import { applyReducedMotion } from '../services/motion';
import { getProfile, getProgress, updateBusinessSection, updateProfile } from '../services/profile';
import { STAGE_GROUPS } from '../data/onboardingQuestions';
import { getNotificationPreferences, updateNotificationPreferences } from '../services/settings';
import { logout } from '../services/auth';
import { getCatalog, getMyPlan, planLabel as planLabelFor } from '../services/plans';
import { dailyTokenMeter, formatTokenMeter } from '../utils/planMeter';
import {
  deleteAccount,
  downloadExport,
  exportData,
  getDataSummary,
  getPrivacyStatus,
  restrictProcessing,
  withdrawConsent,
} from '../services/privacy';

// --- Privacy Center helpers ------------------------------------------------

// `kind` decides which right is exercised, and therefore which endpoint runs:
//   export   -> GET    /privacy/export    (served immediately, downloads a file)
//   summary  -> GET    /privacy/summary   (served immediately, downloads counts —
//               no email delivery exists, so unlike `queued` below, this can't
//               sit on a review queue nobody can ever resolve. "Request data
//               correction" stays `queued` on purpose: there's nothing to
//               download for a fix-my-record request, a person has to do it.)
//   restrict -> POST   /privacy/restrict  (reversible pause)
//   withdraw -> POST   /privacy/withdraw  (revokes consent, keeps the account)
//   delete   -> DELETE /privacy/account   (schedules erasure)
//   queued   -> POST   /settings/privacy  (needs a human; goes on the review queue)
const PRIVACY_ACTIONS = [
  {
    type: 'download_data',
    kind: 'export',
    label: 'Download my data',
    desc: 'Get everything Ally holds about you as JSON — profile, diagnosis sessions and answers, reports, conversations, and what Ally worked out about you.',
    icon: (
      <svg viewBox="0 0 24 24">
        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
        <polyline points="7 10 12 15 17 10" />
        <line x1="12" y1="15" x2="12" y2="3" />
      </svg>
    ),
    confirmTitle: 'Download your data?',
    confirmDesc: 'Ally will assemble a full copy of your data and download it to this device now.',
    confirmColor: '#4338ca',
    confirmBg: '#f0f4ff',
  },
  {
    type: 'view_data',
    kind: 'summary',
    label: 'View data summary',
    desc: 'See how much data Ally holds for you, grouped by what it is — shown here, no download.',
    icon: (
      <svg viewBox="0 0 24 24">
        <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
        <circle cx="12" cy="12" r="3" />
      </svg>
    ),
    confirmTitle: 'View your data summary?',
    confirmDesc: 'Ally will count what it holds under your account and show you the totals, grouped by what the data is. Nothing is downloaded.',
    confirmColor: '#4338ca',
    confirmBg: '#f0f4ff',
  },
  {
    type: 'correct_data',
    kind: 'queued',
    label: 'Request data correction',
    desc: 'Ask us to fix inaccurate or incomplete personal information in your profile or stored records.',
    icon: (
      <svg viewBox="0 0 24 24">
        <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
        <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
      </svg>
    ),
    confirmTitle: 'Request data correction?',
    confirmDesc: 'Our team will review and correct the identified data within 30 days. Tell us what is wrong and what it should say.',
    confirmColor: '#4338ca',
    confirmBg: '#f0f4ff',
    // `prompt` turns the confirm modal into a one-field form. Without it this
    // action said "please add details in the request" above a dialog with
    // nowhere to add them, and posted no details at all -- so every correction
    // reached an admin as "this founder wants something corrected".
    prompt: {
      label: 'What should we correct?',
      placeholder: 'e.g. my company name is spelled wrong — it should be GoXL, not Goxl',
      multiline: true,
      required: false,
    },
  },
  {
    // Sits beside the correction request because it IS one -- the same ask, the
    // same queue, the same 30 days. It is listed separately only because a
    // founder looking for it is looking for the word "email", not "correction".
    type: 'email_change',
    kind: 'queued',
    label: 'Request an email change',
    desc: 'Signed up with the wrong address, or need your account moved to a different one? Ask us to change it — we cannot change it from here ourselves.',
    icon: (
      <svg viewBox="0 0 24 24">
        <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z" />
        <polyline points="22,6 12,13 2,6" />
      </svg>
    ),
    confirmTitle: 'Request an email change?',
    // Says plainly that we will write to the NEW address. A founder who
    // mistyped theirs cannot receive anything at the old one, so "we'll confirm
    // by email" would read as "you will never hear back".
    confirmDesc: 'A person reviews this within 30 days and will contact you at the new address to confirm it is yours. Your sign-in address does not change until then.',
    confirmColor: '#4338ca',
    confirmBg: '#f0f4ff',
    prompt: {
      label: 'New email address',
      placeholder: 'you@example.com',
      type: 'email',
      required: true,
      // Mirrors the server rule. Client-side only to give the answer instantly;
      // the server validates the same thing and is the one that counts.
      validate: (v) => (/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(v.trim())
        ? null
        : 'Enter a valid email address, e.g. you@example.com.'),
    },
  },
  {
    // DPDP s.13: a readily available grievance mechanism. Before this, the
    // Privacy Policy named a Grievance Officer and promised a 48-hour
    // acknowledgement, and the only way to reach them was a `mailto:` -- so a
    // complaint either left the founder's own mail client or did not exist, and
    // nothing could acknowledge what it had never received.
    type: 'grievance',
    kind: 'queued',
    label: 'Raise a privacy complaint',
    desc: 'Unhappy with how we have handled your data? This goes straight to our Grievance Officer, who acknowledges within 48 hours.',
    icon: (
      <svg viewBox="0 0 24 24">
        <path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
        <line x1="12" y1="9" x2="12" y2="13" />
        <line x1="12" y1="17" x2="12.01" y2="17" />
      </svg>
    ),
    confirmTitle: 'Raise a privacy complaint',
    confirmDesc: 'This goes to our Grievance Officer under India’s DPDP Act. We acknowledge within 48 hours and aim to resolve within 30 days.',
    confirmColor: '#b45309',
    confirmBg: '#fffbeb',
    prompt: {
      label: 'What went wrong?',
      placeholder: 'Tell us what happened, and what you would like us to do about it.',
      multiline: true,
      required: true,
    },
  },
  {
    type: 'portability',
    kind: 'export',
    label: 'Export for portability',
    desc: 'Download just the data you gave us — your answers, goals, tasks and conversations — as JSON you can take to another service. Leaves out Ally\'s own analysis.',
    icon: (
      <svg viewBox="0 0 24 24">
        <polyline points="16 3 21 3 21 8" />
        <line x1="4" y1="20" x2="21" y2="3" />
        <polyline points="21 16 21 21 16 21" />
        <line x1="15" y1="15" x2="21" y2="21" />
      </svg>
    ),
    confirmTitle: 'Export your data?',
    confirmDesc: 'Ally will prepare a portable, machine-readable copy and download it now.',
    confirmColor: '#4338ca',
    confirmBg: '#f0f4ff',
  },
  {
    type: 'restrict_processing',
    kind: 'restrict',
    label: 'Restrict data processing',
    desc: 'Pause AI analysis and profiling of your data. Your account stays active but Ally won\'t generate new insights.',
    icon: (
      <svg viewBox="0 0 24 24">
        <circle cx="12" cy="12" r="10" />
        <line x1="4.93" y1="4.93" x2="19.07" y2="19.07" />
      </svg>
    ),
    confirmTitle: 'Restrict data processing?',
    confirmDesc: 'Ally will suspend AI profiling for your account. You can lift this restriction at any time from here.',
    confirmColor: '#92400e',
    confirmBg: '#fffbeb',
  },
  {
    type: 'withdraw_consent',
    kind: 'withdraw',
    label: 'Withdraw consent',
    desc: 'Revoke your consent to AI analysis. Processing pauses immediately and your account stays active — this does not delete anything.',
    icon: (
      <svg viewBox="0 0 24 24">
        <path d="M18.36 6.64A9 9 0 1 1 5.64 6.64" />
        <line x1="12" y1="2" x2="12" y2="12" />
      </svg>
    ),
    confirmTitle: 'Withdraw your consent?',
    confirmDesc: 'Ally will stop analysing your data straight away. Your account and existing records stay intact, and you can give consent again later.',
    confirmColor: '#92400e',
    confirmBg: '#fffbeb',
  },
  {
    type: 'delete_account',
    kind: 'delete',
    label: 'Delete my account',
    desc: 'Request full erasure of your account and all associated data. Scheduled with a 30-day recovery window before it becomes permanent.',
    icon: (
      <svg viewBox="0 0 24 24">
        <polyline points="3 6 5 6 21 6" />
        <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" />
        <path d="M10 11v6M14 11v6" />
        <path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2" />
      </svg>
    ),
    confirmTitle: 'Delete your account?',
    confirmDesc: 'Erasure will be scheduled 30 days from now. Contact support within that window to cancel — after it passes, your data cannot be recovered.',
    confirmColor: '#991b1b',
    confirmBg: '#fff1f2',
  },
];

const TYPE_LABELS = {
  download_data: 'Download data',
  view_data: 'View data summary',
  correct_data: 'Data correction',
  portability: 'Data portability export',
  restrict_processing: 'Restrict processing',
  withdraw_consent: 'Withdraw consent',
  delete_account: 'Account deletion',
  cancel_deletion: 'Deletion cancelled',
  email_change: 'Email change',
  grievance: 'Privacy complaint',
};

function fmtDate(iso) {
  if (!iso) return '';
  return new Date(iso).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' });
}

// ---------------------------------------------------------------------------

export default function FounderProfile() {
  const navigate = useNavigate();
  const [signingOut, setSigningOut] = useState(false);

  /* The real plan, so this page stops insisting everyone is on Free. */
  const [plan, setPlan] = useState(null);
  const [tiers, setTiers] = useState([]);
  // The completeness ring below used to hardcode 100% for every founder,
  // whether their profile was 5% or fully filled in. /profile/progress
  // already computes this server-side (same number /profile/validate's
  // "what's missing" list is built from); this just reads it instead of
  // asserting a number that was never true for most founders.
  //
  // It measures PROFILE FIELDS, not Founder DNA dimensions -- the ring was
  // still labelled "Founder DNA mapped" long after it started reading this
  // endpoint, which is a different quantity entirely. See the label itself.
  const [progressPct, setProgressPct] = useState(null);
  useEffect(() => {
    let cancelled = false;
    // /plans/me knows which tier they are on; the monthly price lives on the
    // /plans catalog, so the figure shown is the same one the pricing page quotes.
    getMyPlan().then(p => { if (!cancelled) setPlan(p); }).catch(() => {});
    getCatalog().then(c => { if (!cancelled) setTiers(c?.plans || []); }).catch(() => {});
    getProgress().then(p => { if (!cancelled && p) setProgressPct(p.percent); }).catch(() => {});
    return () => { cancelled = true; };
  }, []);
  const planTier = plan?.tier || 'free';
  const isFreePlan = planTier === 'free';
  // Was 'Ally Free' whenever plan_name had not arrived -- so a founder who had
  // paid was told they were on Free for as long as the request took. The
  // helper falls back to the tier's real name instead.
  const planLabel = planLabelFor(planTier, plan?.plan_name);
  const monthly = tiers.find(t => t.tier === planTier)?.price_inr;
  const planPrice = isFreePlan ? '₹0' : (monthly ? `₹${monthly.toLocaleString('en-IN')}` : '—');

  /* Revoke the refresh token server-side, clear every local trace, then send
     them to the landing page. Guarded so a double-click cannot fire two
     revokes, the second of which would fail against an already-dead token. */
  const handleSignOut = async () => {
    if (signingOut) return;
    setSigningOut(true);
    await logout();
    navigate('/', { replace: true });
  };
  const { setUser, showToast, startTour } = useApp();
  const [editing, setEditing] = useState(false);

  // Privacy Center state
  const [pendingAction, setPendingAction] = useState(null); // the action object being confirmed
  const [submitting, setSubmitting] = useState(false);
  const [progress, setProgress] = useState('');             // what's happening right now
  const [privacyRequests, setPrivacyRequests] = useState([]);
  const [requestsLoaded, setRequestsLoaded] = useState(false);
  // Collapsed by default -- a founder who's clicked "Download my data" a dozen
  // times over weeks of testing (this happens) would otherwise push the whole
  // Danger Zone section off-screen behind a wall of history rows.
  const [historyOpen, setHistoryOpen] = useState(false);
  const [privacyState, setPrivacyState] = useState(null);   // restriction / deletion standing
  // "View data summary" used to download a JSON file of database table names --
  // it neither viewed anything nor said anything a founder could read. Held here
  // so it can be shown on the page instead.
  const [dataSummary, setDataSummary] = useState(null);
  // Freetext for the actions that carry a `prompt` (correction, email change).
  // Cleared whenever the modal opens or closes so a half-typed address from an
  // abandoned attempt is never silently submitted with the next one.
  const [promptValue, setPromptValue] = useState('');
  const [promptError, setPromptError] = useState('');
  // Ref, not state: state updates are async, so two clicks in the same tick would
  // both see submitting === false. The ref flips synchronously.
  const inFlight = useRef(false);

  const openAction = useCallback((action) => {
    setPromptValue('');
    setPromptError('');
    setPendingAction(action);
  }, []);

  // Load privacy standing + request history on mount (graceful if backend is down)
  useEffect(() => {
    (async () => {
      try {
        const status = await getPrivacyStatus();
        setPrivacyState(status.state ?? null);
        setPrivacyRequests(status.requests ?? []);
      } catch {
        // Fall back to the legacy queue endpoint so the history still renders.
        try {
          const data = await get('/settings/privacy');
          setPrivacyRequests(data.items ?? []);
        } catch { /* backend down — leave empty */ }
      } finally {
        setRequestsLoaded(true);
      }
    })();
  }, []);

  const handleSubmitPrivacyRequest = useCallback(async () => {
    if (!pendingAction || inFlight.current) return;

    // Validate before the spinner starts. A required field that fails should
    // leave the modal open with the message under the box, not close it and
    // surface a server error in a toast the founder has to read twice.
    const prompt = pendingAction.prompt;
    if (prompt) {
      const value = promptValue.trim();
      if (prompt.required && !value) {
        setPromptError(`${prompt.label} is required.`);
        return;
      }
      const invalid = value && prompt.validate ? prompt.validate(value) : null;
      if (invalid) {
        setPromptError(invalid);
        return;
      }
    }
    setPromptError('');

    inFlight.current = true;
    setSubmitting(true);

    const label = TYPE_LABELS[pendingAction.type] ?? pendingAction.label;
    try {
      switch (pendingAction.kind) {
        case 'export': {
          // The two export buttons exercise different rights and now produce
          // different files: 'download_data' is the full right-of-access copy,
          // 'portability' carries only what the founder gave us. Filenames differ
          // so the two are still tellable apart in a downloads folder.
          const portability = pendingAction.type === 'portability';
          setProgress('Assembling your data…');
          const bundle = await exportData(portability ? 'portability' : 'access');
          setProgress('Preparing download…');
          const stamp = new Date().toISOString().slice(0, 10);
          downloadExport(bundle, portability
            ? `ally-portability-export-${stamp}.json`
            : `ally-data-export-${stamp}.json`);
          setPrivacyRequests(prev => [bundle.request, ...prev]);
          showToast(`Export ready — ${bundle.record_count} records downloaded ✓`);
          break;
        }
        case 'summary': {
          // Shown, not downloaded. The button says "View", and a founder asking
          // what we hold should get an answer they can read on the spot rather
          // than a file of table names to decipher.
          setProgress('Counting your data…');
          const summary = await getDataSummary();
          setPrivacyRequests(prev => [summary.request, ...prev]);
          setDataSummary(summary);
          break;
        }
        case 'restrict': {
          setProgress('Pausing processing…');
          const res = await restrictProcessing(true);
          setPrivacyState(res.state);
          setPrivacyRequests(prev => [res.request, ...prev]);
          showToast(res.message);
          break;
        }
        case 'withdraw': {
          setProgress('Withdrawing consent…');
          const res = await withdrawConsent();
          setPrivacyState(res.state);
          setPrivacyRequests(prev => [res.request, ...prev]);
          showToast(res.message);
          break;
        }
        case 'delete': {
          setProgress('Scheduling erasure…');
          const res = await deleteAccount();
          setPrivacyState(res.state);
          setPrivacyRequests(prev => [res.request, ...prev]);
          showToast(res.message);
          // Signed out on the way out, deliberately. Every AI feature is gated
          // on the pending deletion server-side, so staying logged in left the
          // founder inside an app that had quietly stopped working. Signing out
          // makes the request feel final; DeletionPendingGate is what greets
          // them if they come back within the 30-day window and offers the undo.
          setProgress('Signing you out…');
          await logout();
          window.location.href = '/guided/login';
          return;
        }
        default: {
          // Rights that need a human to action — queued for review.
          setProgress('Submitting request…');
          // request_details is sent only when there is something in it. The
          // endpoint forbids unknown keys and treats the field as optional, so
          // an empty string would be a meaningless row for an admin to read.
          const details = promptValue.trim();
          const created = await post('/settings/privacy', {
            request_type: pendingAction.type,
            ...(details ? { request_details: details } : {}),
          });
          setPrivacyRequests(prev => [created, ...prev]);
          showToast(pendingAction.type === 'email_change'
            ? 'Email change requested ✓ — we will contact you at the new address'
            : `${label} request submitted ✓`);
        }
      }
    } catch (err) {
      // A server rejection is real and must surface — never fake success for a
      // right the user believes they just exercised.
      showToast(err.detail || `Could not complete "${label}" — please try again.`);
    } finally {
      inFlight.current = false;
      setSubmitting(false);
      setProgress('');
      setPendingAction(null);
      setPromptValue('');
      setPromptError('');
    }
  }, [pendingAction, promptValue, showToast]);

  const handleResumeProcessing = useCallback(async () => {
    if (inFlight.current) return;
    inFlight.current = true;
    setSubmitting(true);
    setProgress('Resuming processing…');
    try {
      const res = await restrictProcessing(false);
      setPrivacyState(res.state);
      setPrivacyRequests(prev => [res.request, ...prev]);
      showToast(res.message);
    } catch (err) {
      showToast(err.detail || 'Could not lift the restriction — please try again.');
    } finally {
      inFlight.current = false;
      setSubmitting(false);
      setProgress('');
    }
  }, [showToast]);


  // Form fields. These were seeded with a fabricated person, so every founder
  // opened their profile and saw someone else's name, email and phone.
  // phone/location dropped entirely -- product decision: not needed, and
  // neither was ever persisted anyway (PATCH /profile had no field for
  // either), so Edit silently did nothing for them.
  const [form, setForm] = useState({
    name: '', email: '', linkedin: '', stage: '',
  });
  const [, setProfileLoaded] = useState(false);
  const [avatarUrl, setAvatarUrl] = useState(null);
  const [uploadingAvatar, setUploadingAvatar] = useState(false);
  const avatarInputRef = useRef(null);

  useEffect(() => {
    let cancelled = false;
    getProfile()
      .then((p) => {
        if (cancelled || !p) return;
        setForm({
          name: p.full_name || '',
          email: p.email || '',
          linkedin: p.linkedin_url || '',
          // stage_name, not stage_id: the API takes the NAME on write and
          // resolves it (profile/routes.py), and the id is meaningless here.
          stage: p.stage_name || '',
        });
        if (p.avatar_url) setAvatarUrl(p.avatar_url);
      })
      .catch(() => { /* leave the fields empty rather than inventing values */ })
      .finally(() => { if (!cancelled) setProfileLoaded(true); });
    return () => { cancelled = true; };
  }, []);

  /** Upload a new profile photo. Fails loudly (a toast) rather than silently
   * -- a founder who just picked a photo and sees nothing happen assumes it
   * worked, which is worse than being told it didn't. */
  const handleAvatarSelected = async (e) => {
    const file = e.target.files?.[0];
    e.target.value = ''; // allow re-selecting the same file later
    if (!file) return;
    if (file.size > 5 * 1024 * 1024) {
      showToast('That image is too large — please pick one under 5MB.');
      return;
    }
    setUploadingAvatar(true);
    try {
      const form2 = new FormData();
      form2.append('file', file);
      const res = await post('/profile/avatar', form2, { headers: { 'Content-Type': undefined } });
      setAvatarUrl(res.avatar_url);
      // Live-reported: the sidebar kept the OLD photo until a full reload.
      // setAvatarUrl above only updates this page's own copy -- the sidebar
      // (PlatformLayout) reads user.avatar from AppContext, which handleSave
      // already updates for a name change but this upload never touched.
      setUser(prev => ({ ...prev, avatar: res.avatar_url }));
      showToast('Profile photo updated ✓');
    } catch (err) {
      showToast(err?.message || 'Could not upload that photo. Please try again.');
    } finally {
      setUploadingAvatar(false);
    }
  };

  // Preferences Switches. Names on the UI side; the backend's
  // notification_preferences keys are different (in_app_all, email_reminders,
  // ...), so this map is the one place the two vocabularies meet.
  const SWITCH_FIELD = {
    notifications: 'in_app_all',
    renewal: 'email_reminders',
    // Deliberately NOT email_reminders: that one gates the reminder for a
    // discovery call the founder paid for. Sharing it would mean switching off
    // task mail also switches off the reminder for their call.
    taskEmails: 'email_task_reminders',
    reducedMotion: 'reduced_motion',
  };
  const [switches, setSwitches] = useState({
    renewal: true,
    notifications: true,
    taskEmails: true,
    reducedMotion: false,
  });
  const [switchesLoaded, setSwitchesLoaded] = useState(false);

  // Live-reported: toggling any of these, then reloading, silently reset
  // them all to default -- there was no backend call at all, not even
  // localStorage. Loaded from the real preferences on mount now.
  useEffect(() => {
    let cancelled = false;
    getNotificationPreferences()
      .then((prefs) => {
        if (cancelled || !prefs) return;
        setSwitches({
          notifications: prefs.in_app_all ?? true,
          renewal: prefs.email_reminders ?? true,
          taskEmails: prefs.email_task_reminders ?? true,
          reducedMotion: prefs.reduced_motion ?? false,
        });
      })
      .catch(() => { /* leave the defaults -- a stale-but-sane UI beats a broken one */ })
      .finally(() => { if (!cancelled) setSwitchesLoaded(true); });
    return () => { cancelled = true; };
  }, []);

  // Optimistic, same shape as everywhere else in this session (Plan Your Day,
  // attachments): flip locally so the switch feels instant, roll back and
  // toast if the save actually fails.
  const toggleSwitch = async (key) => {
    const next = !switches[key];
    setSwitches(prev => ({ ...prev, [key]: next }));
    // Reduced motion has to take effect on the spot, not on the next reload:
    // someone turning it on is asking the movement to stop now. Rolled back
    // below with the switch if the save fails, so the page never disagrees
    // with the server about what is set.
    if (key === 'reducedMotion') applyReducedMotion(next);
    try {
      await updateNotificationPreferences({ [SWITCH_FIELD[key]]: next });
    } catch (err) {
      setSwitches(prev => ({ ...prev, [key]: !next }));
      if (key === 'reducedMotion') applyReducedMotion(!next);
      showToast(err?.message || 'Could not save that preference — please try again.');
    }
  };

  const [savingProfile, setSavingProfile] = useState(false);

  /**
   * Persist the profile. This previously only wrote to React context and always
   * claimed success, so an edit survived until the next reload and then vanished.
   *
   * Only the fields PATCH /profile actually accepts are sent. Email is owned by
   * the identity provider, and phone/location have no field on the API at all --
   * see the note beside those inputs.
   */
  const handleSave = async () => {
    if (savingProfile) return;
    setSavingProfile(true);
    try {
      await updateProfile({
        full_name: form.name.trim(),
        linkedin_url: form.linkedin.trim(),
      });
      // Stage lives on the business section, not PATCH /profile. Sent only
      // when set, so opening Edit and saving without touching it cannot clear
      // a stage the founder already has.
      if (form.stage) await updateBusinessSection({ stage: form.stage });
      setUser(prev => ({ ...prev, name: form.name.trim() }));
      setEditing(false);
      showToast('Profile saved ✓');
    } catch (err) {
      // Stay in edit mode so the founder does not lose what they typed.
      showToast(err?.message || 'Could not save your profile. Please try again.');
    } finally {
      setSavingProfile(false);
    }
  };

  return (
    <div className="dc-container">
      {/* What Ally holds, shown rather than downloaded. Grouped and labelled by
          the server so this page, the help bot and anything else describing a
          founder's data use one set of words. */}
      {dataSummary && (
        <div className="pr-privacy-overlay" onClick={() => setDataSummary(null)}>
          <div
            className="pr-privacy-modal"
            onClick={e => e.stopPropagation()}
            role="dialog"
            aria-modal="true"
            aria-labelledby="pr-summary-title"
            style={{ maxWidth: 520, textAlign: 'left' }}
          >
            <h3 id="pr-summary-title" style={{ textAlign: 'left' }}>What Ally holds about you</h3>
            <p style={{ textAlign: 'left' }}>
              {dataSummary.total_records} records in total, as of{' '}
              {fmtDate(dataSummary.generated_at)}.
            </p>

            <div style={{ margin: '16px 0', display: 'flex', flexDirection: 'column', gap: 2 }}>
              {(dataSummary.categories ?? []).map(c => (
                <div
                  key={c.key}
                  style={{
                    display: 'flex', alignItems: 'baseline', justifyContent: 'space-between',
                    gap: 16, padding: '10px 0', borderTop: '1px solid var(--pr-line, #e8e3da)',
                  }}
                >
                  <div style={{ minWidth: 0 }}>
                    <div style={{ fontWeight: 600, fontSize: 14 }}>{c.label}</div>
                    <div style={{ fontSize: 12.5, opacity: 0.72, marginTop: 2 }}>{c.description}</div>
                  </div>
                  <div style={{ fontVariantNumeric: 'tabular-nums', fontWeight: 600, fontSize: 15 }}>
                    {c.count}
                  </div>
                </div>
              ))}
            </div>

            <p style={{ textAlign: 'left', fontSize: 13, opacity: 0.8 }}>
              This is the count, not the contents. To read the data itself, use
              “Download my data”.
            </p>

            <div className="pr-privacy-modal-actions">
              <button
                className="pr-privacy-cancel-btn"
                onClick={() => setDataSummary(null)}
                type="button"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Confirm modal */}
      {pendingAction && (
        <div className="pr-privacy-overlay" onClick={() => !submitting && setPendingAction(null)}>
          <div className="pr-privacy-modal" onClick={e => e.stopPropagation()}>
            <div
              className="pr-privacy-modal-icon"
              style={{ background: pendingAction.confirmBg }}
            >
              <svg viewBox="0 0 24 24" style={{ width: 22, height: 22, fill: 'none', stroke: pendingAction.confirmColor, strokeWidth: 2.2 }}>
                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
              </svg>
            </div>
            <h3>{pendingAction.confirmTitle}</h3>
            <p>{pendingAction.confirmDesc}</p>

            {/* One field, for the actions that need the founder to say what they
                actually want. Labelled properly and wired to the error with
                aria-describedby: this is the only input in the Privacy Center,
                and a screen-reader user who cannot hear why Confirm did nothing
                is stuck with no way forward. */}
            {pendingAction.prompt && (
              <div style={{ textAlign: 'left', margin: '4px 0 18px' }}>
                <label
                  htmlFor="pr-privacy-prompt"
                  style={{ display: 'block', fontSize: 13, fontWeight: 600, marginBottom: 6 }}
                >
                  {pendingAction.prompt.label}
                  {pendingAction.prompt.required && (
                    <span aria-hidden="true" style={{ color: '#b91c1c' }}> *</span>
                  )}
                </label>
                {pendingAction.prompt.multiline ? (
                  <textarea
                    id="pr-privacy-prompt"
                    className="pr-privacy-prompt-input"
                    rows={3}
                    value={promptValue}
                    placeholder={pendingAction.prompt.placeholder}
                    maxLength={2000}
                    disabled={submitting}
                    aria-required={!!pendingAction.prompt.required}
                    aria-invalid={!!promptError}
                    aria-describedby={promptError ? 'pr-privacy-prompt-err' : undefined}
                    onChange={e => { setPromptValue(e.target.value); setPromptError(''); }}
                  />
                ) : (
                  <input
                    id="pr-privacy-prompt"
                    className="pr-privacy-prompt-input"
                    type={pendingAction.prompt.type || 'text'}
                    value={promptValue}
                    placeholder={pendingAction.prompt.placeholder}
                    maxLength={2000}
                    disabled={submitting}
                    autoComplete="email"
                    aria-required={!!pendingAction.prompt.required}
                    aria-invalid={!!promptError}
                    aria-describedby={promptError ? 'pr-privacy-prompt-err' : undefined}
                    onChange={e => { setPromptValue(e.target.value); setPromptError(''); }}
                    onKeyDown={e => { if (e.key === 'Enter' && !submitting) handleSubmitPrivacyRequest(); }}
                  />
                )}
                {promptError && (
                  <div
                    id="pr-privacy-prompt-err"
                    role="alert"
                    style={{ color: '#b91c1c', fontSize: 12.5, marginTop: 6 }}
                  >
                    {promptError}
                  </div>
                )}
              </div>
            )}

            <div className="pr-privacy-modal-actions">
              <button
                className="pr-privacy-cancel-btn"
                onClick={() => setPendingAction(null)}
                disabled={submitting}
                type="button"
              >
                Cancel
              </button>
              <button
                className="pr-privacy-confirm-btn"
                onClick={handleSubmitPrivacyRequest}
                disabled={submitting}
                type="button"
                style={{ background: pendingAction.confirmColor }}
              >
                {submitting
                  ? (progress || 'Working…')
                  : pendingAction.kind === 'summary' ? 'Show me'
                  : pendingAction.kind === 'export' ? 'Download now'
                  : 'Confirm'}
              </button>
            </div>
          </div>
        </div>
      )}
      {/* Settings Hero Card */}
      <div className="fd-hero stagger d1" style={{ padding: '26px 30px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '20px', flex: 1, minWidth: 0 }}>
          {/* Avatar Wrap */}
          <div style={{ position: 'relative', flexShrink: 0 }}>
            <div
              className="fd-avatar"
              style={{
                width: '74px',
                height: '74px',
                borderRadius: '50%',
                display: 'grid',
                placeItems: 'center',
                fontFamily: 'var(--display)',
                fontWeight: 800,
                fontSize: '24px',
                color: '#06231a',
                background: avatarUrl ? undefined : 'linear-gradient(135deg, #34d399, #A8D94A)',
                boxShadow: '0 0 0 3px rgba(255,255,255,0.08), 0 8px 24px -6px rgba(0,0,0,0.5)',
                overflow: 'hidden',
              }}
            >
              {avatarUrl ? (
                <img
                  src={avatarUrl}
                  alt=""
                  style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                />
              ) : (
                /* Was the literal "AS" — a mock founder's initials, rendered
                   directly above every real founder's own name. */
                form.name
                  .split(' ')
                  .filter(Boolean)
                  .slice(0, 2)
                  .map(w => w[0].toUpperCase())
                  .join('') || '?'
              )}
            </div>
            {/* Was dead -- no onClick at all -- now wired to a real upload
                endpoint (see handleAvatarSelected below). */}
            <input
              ref={avatarInputRef}
              type="file"
              accept="image/png,image/jpeg,image/webp"
              aria-label="Upload profile photo"
              style={{ display: 'none' }}
              onChange={handleAvatarSelected}
            />
            <button
              className="fp-cam"
              type="button"
              aria-label="Change profile photo"
              disabled={uploadingAvatar}
              onClick={() => avatarInputRef.current?.click()}
              style={{
                position: 'absolute',
                right: '-2px',
                bottom: '-2px',
                width: '24px',
                height: '24px',
                borderRadius: '50%',
                display: 'grid',
                placeItems: 'center',
                background: '#0E2A1C',
                border: '1.5px solid rgba(255,255,255,0.2)',
                color: uploadingAvatar ? '#5c7568' : '#34d399',
                cursor: uploadingAvatar ? 'wait' : 'pointer'
              }}
            >
              <svg viewBox="0 0 24 24" style={{ width: 12, height: 12, fill: 'none', stroke: 'currentColor', strokeWidth: 2 }}>
                <path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z" />
                <circle cx="12" cy="13" r="4" />
              </svg>
            </button>
          </div>

          <div style={{ minWidth: 0, textAlign: 'left' }}>
            <div className="fd-hero-kicker" style={{ marginBottom: '6px' }}>Founder Profile · Read by Ally</div>
            <h2 className="fd-hero-title" style={{ fontSize: '24px', margin: '0 0 2px' }}>{form.name}</h2>
            {/* Was hardcoded to "Founder & CEO - BrightLoom" for every founder. */}
            {form.email && (
              <div style={{ fontSize: '13.5px', color: 'var(--on-dark-muted)', marginBottom: '10px' }}>
                {form.email}
              </div>
            )}
            {/* The location/link/star chip row that used to live here was
                three pieces of fake UI: a location value duplicating the
                field below, and two badges (link/star icon) hardcoded to the
                literal text "1" with no backing data or function anywhere in
                the app -- not clickable, not connected to anything. Removed
                rather than invented a meaning for them. */}
          </div>
        </div>

        {/* Ring Score -- real /profile/progress percent, not a fixed 100%.
            circumference = 2*pi*r(44) =~ 276.46; offset 0 is a full ring, so
            an EMPTY profile needs the full circumference as its offset, not 0. */}
        <div style={{ flexShrink: 0, textAlign: 'center', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '6px' }}>
          <div className="rep-ring" style={{ width: '74px', height: '74px' }}>
            <svg viewBox="0 0 100 100">
              <circle className="bg" cx="50" cy="50" r="44" strokeWidth="8" />
              <circle
                className="fg"
                cx="50"
                cy="50"
                r="44"
                strokeWidth="8"
                style={{ strokeDasharray: 276, strokeDashoffset: 276 * (1 - (progressPct ?? 0) / 100) }}
              />
            </svg>
            <div className="rep-ring-c">
              <b style={{ fontSize: '20px' }}>{progressPct != null ? `${progressPct}%` : '—'}</b>
              <small style={{ fontSize: '6.5px', letterSpacing: '0.08em', marginTop: '1px' }}>DONE</small>
            </div>
          </div>
          {/* "Profile complete", not "Founder DNA mapped". The number here is
              /profile/progress -- the share of profile FIELDS filled in (stage,
              experience, problem statement, what you're building, who you serve
              ...), which is the same set /profile/validate lists as missing. It
              has never had anything to do with the 14 Founder DNA dimensions.
              The old label was measurably wrong rather than merely loose: a
              founder whose DNA data had been wiped to zero resolved dimensions
              still read "64% Founder DNA mapped". Renaming the label rather than
              repointing the ring, because profile completeness is genuinely the
              useful number on a profile page -- it is the one the founder can
              act on from here. */}
          <div className="fd-hero-label" style={{ fontSize: '9px', color: 'var(--on-dark-muted)', maxWidth: '90px', lineHeight: 1.2 }}>
            Profile complete
          </div>
        </div>
      </div>

      {/* ── Founder Identity ── */}
      <div className="pr-sec-head stagger d2">
        <h3 className="pr-sec-title">Founder Identity</h3>
        <span className="pr-sec-sub">The human Ally is building with.</span>
      </div>

      <div className="pr-card stagger d2">
        <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: '14px' }}>
          {editing ? (
            <div style={{ display: 'flex', gap: '8px' }}>
              <button
                className="pr-row-btn"
                onClick={() => setEditing(false)}
                type="button"
              >
                Cancel
              </button>
              <button
                className="pr-row-btn"
                style={{ background: 'var(--emerald, #10B981)', color: '#06231a', borderColor: 'transparent' }}
                onClick={handleSave}
                disabled={savingProfile}
                type="button"
              >
                {savingProfile ? 'Saving…' : 'Save'}
              </button>
            </div>
          ) : (
            <button
              className="pr-row-btn"
              onClick={() => setEditing(true)}
              type="button"
            >
              <svg viewBox="0 0 24 24">
                <path d="M12 20h9M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z" />
              </svg>
              Edit
            </button>
          )}
        </div>

        <div className="pr-grid">
          <div className="pr-field">
            <label className="pr-lbl" htmlFor="pr-name">Full Name</label>
            {editing ? (
              <input
                id="pr-name"
                className="pr-input"
                value={form.name}
                onChange={e => setForm({ ...form, name: e.target.value })}
              />
            ) : (
              <div className="pr-val">{form.name}</div>
            )}
          </div>

          {/* Stage. Editable HERE and not only in guided onboarding, because a
              founder who reached the app without finishing that flow had no way
              to set it at all -- founders.stage_id was NULL for 27 of 45 live
              founders, and this page counted it toward "profile complete" while
              offering nothing to complete it with.

              It is not cosmetic. Founder DNA and Current Problem pick their
              question bank by stage group, the recommendation engine filters
              interventions by stage_id, and the report chooses its tone
              (Validator / Compass / Auditor) by stage -- all of which fall back
              to a default or switch off entirely when it is unset. */}
          <div className="pr-field">
            <label className="pr-lbl" htmlFor="pr-stage">Stage</label>
            {editing ? (
              <select
                id="pr-stage"
                className="pr-input"
                value={form.stage}
                onChange={e => setForm({ ...form, stage: e.target.value })}
              >
                <option value="">Select your stage…</option>
                {STAGE_GROUPS.map(g => (
                  <optgroup key={g.key} label={`${g.group} — ${g.label}`}>
                    {g.stages.map(st => (
                      <option key={st.name} value={st.name}>
                        {st.name} — {st.blurb}
                      </option>
                    ))}
                  </optgroup>
                ))}
              </select>
            ) : (
              <div className="pr-val">
                {form.stage || 'Not set — add this so Ally can tailor your diagnosis'}
              </div>
            )}
          </div>

          <div className="pr-field">
            <div className="pr-lbl">Email</div>
            {/* Email comes from the Google/LinkedIn identity, so it is not editable
                here -- offering an input implied a change we cannot persist.
                But "you cannot change this" is only half an answer, and the
                founder who most needs the other half is the one who mistyped it
                and is now reading their own wrong address. So this says where to
                go, on the field itself, rather than leaving them to find the
                Privacy Center on a hunch. */}
            <div className="pr-val">{form.email || '—'}</div>
            <button
              type="button"
              className="pr-inline-link"
              onClick={() => openAction(PRIVACY_ACTIONS.find(a => a.type === 'email_change'))}
            >
              Wrong address? Request a change
            </button>
          </div>

          {/* Phone and Location removed -- not needed here per product
              decision, and neither was ever persisted (PATCH /profile has no
              field for either), so Edit silently did nothing for them with
              no indication why. */}

          <div className="pr-field" style={{ gridColumn: '1 / -1' }}>
            <label className="pr-lbl" htmlFor="pr-linkedin">LinkedIn</label>
            {editing ? (
              <input
                id="pr-linkedin"
                type="url"
                className="pr-input"
                placeholder="https://linkedin.com/in/your-profile"
                pattern="https?://.+"
                value={form.linkedin}
                onChange={e => setForm({ ...form, linkedin: e.target.value })}
              />
            ) : form.linkedin ? (
              <a
                className="pr-val"
                href={/^https?:\/\//.test(form.linkedin) ? form.linkedin : `https://${form.linkedin}`}
                target="_blank"
                rel="noopener noreferrer"
                style={{ color: 'var(--emerald, #10B981)', textDecoration: 'underline' }}
              >
                {form.linkedin}
              </a>
            ) : (
              <div className="pr-val">Not set</div>
            )}
          </div>
        </div>
      </div>

      {/* ── Subscription & billing ── */}
      <div className="pr-sec-head stagger d3">
        <h3 className="pr-sec-title">Subscription & billing</h3>
        <span className="pr-sec-sub">Your plan, renewal and invoices.</span>
      </div>

      <div className="pr-card stagger d3" style={{ paddingBottom: '26px' }}>
        {/* Plan display row */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '20px', textSelf: 'flex-start', textAlign: 'left' }}>
          <div style={{ display: 'flex', gap: '14px', alignItems: 'flex-start' }}>
            <div
              style={{
                width: '40px',
                height: '40px',
                borderRadius: '50%',
                background: 'rgba(27,67,50,0.06)',
                color: 'var(--forest, #1b4332)',
                display: 'grid',
                placeItems: 'center',
                flexShrink: 0
              }}
            >
              <svg viewBox="0 0 24 24" style={{ width: 20, height: 20, fill: 'none', stroke: 'currentColor', strokeWidth: 1.8 }}>
                <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
                <path d="M7 11V7a5 5 0 0 1 10 0v4" />
              </svg>
            </div>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                {/* Every value in this block was hardcoded to the free tier --
                    name, badge, blurb and "₹0 forever" -- so a founder on Pro
                    was told they were on Free, directly above an Upgrade
                    button. The sidebar two inches away read the real plan. */}
                <b style={{ fontSize: '15px', color: 'var(--forest, #1b4332)' }}>{planLabel}</b>
                <span
                  style={{
                    fontSize: '8.5px',
                    fontWeight: 800,
                    letterSpacing: '0.04em',
                    textTransform: 'uppercase',
                    background: isFreePlan ? '#e2e8f0' : '#d1fae5',
                    color: isFreePlan ? '#475569' : '#065f46',
                    padding: '3px 8px',
                    borderRadius: '4px'
                  }}
                >
                  {planTier} Plan
                </span>
              </div>
              <div style={{ fontSize: '12px', color: 'var(--muted-2)', marginTop: '4px' }}>
                {isFreePlan
                  ? "You're on the free plan — upgrade anytime."
                  : 'Your subscription is active.'}
              </div>
            </div>
          </div>
          <div style={{ textAlign: 'right' }}>
            <b style={{ fontSize: '20px', color: 'var(--ink, #16241c)', display: 'block', lineHeight: 1 }}>
              {planPrice}
            </b>
            <span style={{ fontSize: '10.5px', color: 'var(--muted-2)' }}>
              {isFreePlan ? 'forever' : 'per month'}
            </span>
          </div>
        </div>

        {/* Upgrade button */}
        <button
          className="btn btn-primary"
          onClick={() => navigate('/app/billing')}
          style={{
            width: '100%',
            background: 'var(--forest, #1b4332)',
            color: '#ffffff',
            fontWeight: 700,
            padding: '11px 18px',
            borderRadius: '10px',
            justifyContent: 'center',
            marginBottom: '26px'
          }}
          type="button"
        >
          <svg viewBox="0 0 24 24" style={{ width: 14, height: 14, fill: 'none', stroke: 'currentColor', strokeWidth: 2.2 }}>
            <line x1="12" y1="19" x2="12" y2="5" />
            <polyline points="5 12 12 5 19 12" />
          </svg>
          Upgrade plan
        </button>

        {/* Usage statistics header -- was "This month's usage", which was
            wrong for both rows below it: chat resets DAILY (daily_token_usage
            is keyed by UTC date, not month) and diagnosis is a LIFETIME cap,
            not a monthly one. Neither row is monthly, so the header no longer
            claims a single shared window; each row states its own. */}
        <div
          style={{
            fontSize: '9.5px',
            fontWeight: 800,
            letterSpacing: '0.08em',
            textTransform: 'uppercase',
            color: 'var(--muted-2)',
            marginBottom: '16px',
            textAlign: 'left'
          }}
        >
          Usage
        </div>

        {/* Usage meters list */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', marginBottom: '26px' }}>
          {/* Chat usage -- live-confirmed this row and the diagnosis row below
              it were hardcoded literal text ("18 / 20", "1 / 1") for every
              founder regardless of their actual plan or usage; a founder who
              had never run a diagnosis at all saw "1 / 1", indistinguishable
              from having used their only free one. Both now read the same
              /plans/me response this page already fetches (see `plan` above)
              -- daily_tokens_used/_limit are the identical numbers the chat
              gate itself enforces, not a second, divergeable copy. */}
          <div className="pr-usage-row">
            <div className="pr-usage-label-row">
              <div className="pr-usage-title">
                <svg viewBox="0 0 24 24">
                  <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
                </svg>
                Talk to Ally
              </div>
              <span className={`pr-usage-val${dailyTokenMeter(plan).atLimit ? ' is-full' : ''}`}>
                {plan
                  ? `${formatTokenMeter(plan)}${dailyTokenMeter(plan).atLimit ? ' — limit reached' : ' today'}`
                  : '— / —'}
              </span>
            </div>
            <div className="pr-usage-track">
              <div
                className={`pr-usage-fill${dailyTokenMeter(plan).atLimit ? ' is-full' : ''}`}
                style={{ width: `${dailyTokenMeter(plan).pct}%` }}
              />
            </div>
          </div>

          {/* Business diagnosis usage -- diagnosis_usage.limit is null for an
              unlimited plan (0 in the catalog means "no cap", per
              diagnosis/service.py's own convention); shown as an unbounded
              meter rather than inventing a denominator. */}
          <div className="pr-usage-row">
            <div className="pr-usage-label-row">
              <div className="pr-usage-title">
                <svg viewBox="0 0 24 24">
                  <circle cx="12" cy="12" r="10" />
                  <line x1="12" y1="6" x2="12" y2="18" />
                  <line x1="6" y1="12" x2="18" y2="12" />
                </svg>
                AI Business Diagnosis
              </div>
              <span className="pr-usage-val">
                {plan
                  ? (plan.diagnosis_usage?.limit != null
                      ? `${plan.diagnosis_usage.used} / ${plan.diagnosis_usage.limit} lifetime`
                      : `${plan.diagnosis_usage?.used ?? 0} completed`)
                  : '— / —'}
              </span>
            </div>
            <div className="pr-usage-track">
              <div
                className="pr-usage-fill"
                style={{
                  width: plan?.diagnosis_usage?.limit
                    ? `${Math.min(100, Math.round((plan.diagnosis_usage.used / plan.diagnosis_usage.limit) * 100))}%`
                    : '0%',
                }}
              />
            </div>
          </div>

          {/* Document analysis -- live product decision: this is included on
              every plan, Free included, not a Pro-only feature. It has no
              meter of its own because it doesn't spend a separate budget --
              an uploaded document is analysed out of the same daily chat
              token allowance shown above, so a second progress bar here would
              just be showing the same number twice. Was previously a static
              "Upgrade to Pro" badge over a disabled track with no backend
              behind it at all -- pure fiction, removed. */}
          <div className="pr-usage-row">
            <div className="pr-usage-label-row">
              <div className="pr-usage-title">
                <svg viewBox="0 0 24 24">
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                  <polyline points="14 2 14 8 20 8" />
                </svg>
                Document Analysis
              </div>
              <span className="pr-usage-val" style={{ color: 'var(--muted-2)', fontWeight: 700 }}>
                Included
              </span>
            </div>
            <div style={{ fontSize: '11px', color: 'var(--muted-2)', marginTop: '2px' }}>
              Upload a document to Ally Chat — it's analysed out of your chat allowance above.
            </div>
          </div>
        </div>
        {/* Team Members was a hardcoded "1 / 1" with nothing behind it -- no
            team-member model, no invite flow, no backend reference anywhere
            in the codebase. Removed rather than wired up: not a real feature
            for this product. */}

        {/* Email reminders switch.
            WAS "Renewal reminder / Get notified about new features and offers",
            which described a marketing opt-in. It is wired to
            notification_preferences.email_reminders -- the ONLY consumer of which
            is app/services/discovery_notifications.py, gating the 24h and 1h
            reminders for a discovery call. So a founder declining "offers" was
            silently switching off the reminders for a discovery call they had paid for
            for. Relabelled to what it actually controls. If marketing email is
            ever sent, it needs its own flag -- not this one. */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderTop: '1px solid var(--bd)', paddingTop: '20px' }}>
          <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
            <div
              style={{
                width: '32px',
                height: '32px',
                borderRadius: '50%',
                background: 'rgba(27,67,50,0.06)',
                color: 'var(--forest, #1b4332)',
                display: 'grid',
                placeItems: 'center',
                flexShrink: 0
              }}
            >
              <svg viewBox="0 0 24 24" style={{ width: 15, height: 15, fill: 'none', stroke: 'currentColor', strokeWidth: 1.8 }}>
                <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
                <path d="M13.73 21a2 2 0 0 1-3.46 0" />
              </svg>
            </div>
            <div style={{ textAlign: 'left' }}>
              <div style={{ fontSize: '13px', fontWeight: 650, color: 'var(--ink, #16241c)' }}>Call reminders by email</div>
              <div style={{ fontSize: '11px', color: 'var(--muted-2)', marginTop: '2px' }}>
                Reminders before a discovery call you have booked
              </div>
            </div>
          </div>
          <button
            className={`pr-switch${switches.renewal ? ' on' : ''}`}
            onClick={() => toggleSwitch('renewal')}
            type="button"
            role="switch"
            aria-checked={switches.renewal}
            aria-label="Call reminders by email"
          />
        </div>

        {/* ADDED 2026-09-11, alongside the task email itself. The backend has
            read notification_preferences.email_task_reminders since task mail
            shipped, and every one of those emails signs off telling the founder
            to "turn off task emails in Profile > Notifications" -- a control
            that did not exist on this page. Pro founders now get an email every
            time they schedule a task, so the one instruction the email gives
            them had better be true. */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderTop: '1px solid var(--bd)', paddingTop: '20px', marginTop: '20px' }}>
          <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
            <div
              style={{
                width: '32px',
                height: '32px',
                borderRadius: '50%',
                background: 'rgba(27,67,50,0.06)',
                color: 'var(--forest, #1b4332)',
                display: 'grid',
                placeItems: 'center',
                flexShrink: 0
              }}
            >
              <svg viewBox="0 0 24 24" style={{ width: 15, height: 15, fill: 'none', stroke: 'currentColor', strokeWidth: 1.8 }}>
                <rect x="3" y="4" width="18" height="18" rx="2" />
                <path d="M16 2v4M8 2v4M3 10h18M9 16l2 2 4-4" />
              </svg>
            </div>
            <div style={{ textAlign: 'left' }}>
              <div style={{ fontSize: '13px', fontWeight: 650, color: 'var(--ink, #16241c)' }}>Task emails</div>
              <div style={{ fontSize: '11px', color: 'var(--muted-2)', marginTop: '2px' }}>
                A confirmation when you schedule something in Plan Your Day
              </div>
            </div>
          </div>
          <button
            className={`pr-switch${switches.taskEmails ? ' on' : ''}`}
            onClick={() => toggleSwitch('taskEmails')}
            type="button"
            role="switch"
            aria-checked={switches.taskEmails}
            aria-label="Task emails"
          />
        </div>
      </div>

      {/* ── Preferences ── */}
      <div className="pr-sec-head stagger d4">
        <h3 className="pr-sec-title">Preferences</h3>
        <span className="pr-sec-sub">How the workspace behaves.</span>
      </div>

      <div className="pr-card stagger d4">
        {/* HIDDEN 2026-09-05: the "Notifications" switch, described as
            "Report updates, replies and reminders".

            It is wired to notification_preferences.in_app_all, which persists
            correctly and which NOTHING reads -- there are no in-app
            notifications for it to turn off, so flipping it changed nothing
            whichever way it was set. A visible switch that does nothing teaches
            founders that our settings are decorative, which is expensive on a
            page whose whole job is letting them change something.

            Hidden rather than deleted: the flag, the API and the stored value
            are all still there and still correct, so when in-app notifications
            exist this becomes a matter of deleting this comment. Until then
            help answer 257 tells founders the truth about it.

            The state and toggle handler are deliberately left in place too --
            they cost nothing and keep the switch a one-line restore. */}

        <div className="pr-settings-row">
          <div className="pr-settings-info">
            <span className="pr-settings-title">Reduced motion</span>
            <span className="pr-settings-desc">Minimise animations across the workspace</span>
          </div>
          <button
            className={`pr-switch${switches.reducedMotion ? ' on' : ''}`}
            onClick={() => toggleSwitch('reducedMotion')}
            type="button"
            role="switch"
            aria-checked={switches.reducedMotion}
            aria-label="Reduced motion"
          />
        </div>

        {/* REMOVED 2026-09-05: the "Private mode" switch, which read
            "Keep business data anonymised in aggregate insights".
            That sentence told a founder their business data goes into aggregate
            insights by default and that this switch anonymises it. Neither was
            true: nothing anywhere read the flag, and there are no aggregate
            insights in the product. Removed rather than reworded -- a privacy
            control that does nothing is worse than no control, and describing a
            data use we do not have is worse again. If aggregate insights are
            ever built, the opt-out goes in the privacy policy BEFORE it goes on
            this page. */}

        <div className="pr-settings-row">
          <div className="pr-settings-info">
            <span className="pr-settings-title">Product tour</span>
            <span className="pr-settings-desc">Replay the guided walkthrough of every section in Ally</span>
          </div>
          <button
            className="pr-row-btn"
            onClick={startTour}
            type="button"
          >
            <svg viewBox="0 0 24 24">
              <polygon points="5 3 19 12 5 21 5 3" />
            </svg>
            Replay tour
          </button>
        </div>
      </div>

      {/* ── Privacy Center ── */}
      <div className="pr-sec-head stagger d5">
        <h3 className="pr-sec-title">Privacy Center</h3>
        {/* DPDP only. GDPR was claimed here and nowhere else -- not in the
            Privacy Policy, and the team decided on 2026-09-06 that it does not
            apply to us. Claiming a regime you do not intend to honour invites
            the obligation without any of the preparation. */}
        <span className="pr-sec-sub">
          Your data rights under India&rsquo;s DPDP Act — requests are reviewed within 30 days.
        </span>
      </div>

      {/* Makes the Privacy Policy's promise true. It says preferences can be
          changed "at any time through the cookie banner"; until this existed
          the banner could never be reopened, so the only way to withdraw was
          to clear site data by hand. */}
      <div className="pr-card stagger d5" style={{ display: 'flex', alignItems: 'center',
                                                   justifyContent: 'space-between', gap: 16 }}>
        <div>
          <div style={{ fontWeight: 600 }}>Cookie preferences</div>
          <div className="pr-sec-sub">
            Change what you allow. Essential cookies keep you signed in and cannot be turned off.
          </div>
        </div>
        <button
          type="button"
          className="pr-privacy-btn"
          onClick={() => window.dispatchEvent(new Event('ally:open-cookie-preferences'))}
        >
          Change
        </button>
      </div>

      <div className="pr-card stagger d5">
        {/* Current standing — only rendered when something is actually in effect,
            so the common case stays uncluttered. */}
        {privacyState?.deletion_pending && (
          <div className="pr-privacy-banner" role="status" style={{
            background: '#fff1f2', border: '1px solid #fecdd3', borderRadius: 10,
            padding: '12px 14px', marginBottom: 14, color: '#991b1b', fontSize: 13,
          }}>
            {/* Was "Contact support before then to cancel" -- untrue since
                DeletionPendingGate shipped: signing in again offers a one-click
                cancel, and the founder can undo it themselves. Sending them to
                email for something the product already does is the kind of
                answer that makes a support page feel abandoned. */}
            <strong>Account deletion scheduled.</strong>{' '}
            Your data will be erased on {fmtDate(privacyState.deletion_scheduled_at)}. You can
            still change your mind — sign in again before then and choose “Cancel deletion &amp;
            continue”, or email support if you would rather we did it for you.
          </div>
        )}
        {privacyState?.processing_restricted && !privacyState?.deletion_pending && (
          <div className="pr-privacy-banner" role="status" style={{
            background: '#fffbeb', border: '1px solid #fde68a', borderRadius: 10,
            padding: '12px 14px', marginBottom: 14, color: '#92400e', fontSize: 13,
            display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12,
          }}>
            <span>
              <strong>Processing is paused.</strong>{' '}
              Ally isn&apos;t generating new insights
              {privacyState.processing_restricted_at
                ? ` (since ${fmtDate(privacyState.processing_restricted_at)})`
                : ''}.
            </span>
            <button
              className="pr-privacy-btn"
              onClick={handleResumeProcessing}
              disabled={submitting}
              type="button"
              id="privacy-btn-resume"
              style={{ flexShrink: 0 }}
            >
              {submitting ? (progress || 'Working…') : 'Resume'}
            </button>
          </div>
        )}

        {PRIVACY_ACTIONS.map((action) => (
          <div className="pr-privacy-action" key={action.type}>
            <div className="pr-privacy-action-info">
              <div className="pr-privacy-action-title">
                <span style={{ width: 16, height: 16, flexShrink: 0, display: 'inline-flex', alignItems: 'center', color: '#4338ca' }}>
                  <svg viewBox="0 0 24 24" style={{ width: 15, height: 15, fill: 'none', stroke: 'currentColor', strokeWidth: 2.2 }}>
                    {action.icon.props.children}
                  </svg>
                </span>
                {action.label}
              </div>
              <div className="pr-privacy-action-desc">{action.desc}</div>
            </div>
            <button
              className="pr-privacy-btn"
              onClick={() => openAction(action)}
              type="button"
              id={`privacy-btn-${action.type}`}
              disabled={
                submitting ||
                (action.kind === 'restrict' && privacyState?.processing_restricted) ||
                (action.kind === 'delete' && privacyState?.deletion_pending)
              }
            >
              <svg viewBox="0 0 24 24">
                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
              </svg>
              {action.kind === 'restrict' && privacyState?.processing_restricted ? 'Paused'
                : action.kind === 'delete' && privacyState?.deletion_pending ? 'Scheduled'
                /* 'summary' shows on the page now, so promising a download here
                   would be the third thing on this row contradicting itself. */
                : action.kind === 'summary' ? 'View'
                : action.kind === 'export' ? 'Download'
                : 'Request'}
            </button>
          </div>
        ))}

        {/* Request history — collapsed by default; a founder who's clicked
            "Download my data" repeatedly over time otherwise gets a long wall
            of rows here instead of a card. */}
        {requestsLoaded && privacyRequests.length > 0 && (
          <div className="pr-privacy-history">
            <button
              type="button"
              className="pr-privacy-history-toggle"
              onClick={() => setHistoryOpen(o => !o)}
              aria-expanded={historyOpen}
            >
              <span>Submitted requests</span>
              <span className="pr-privacy-history-toggle-right">
                <span className="pr-privacy-history-count">{privacyRequests.length}</span>
                <svg
                  viewBox="0 0 24 24"
                  className="pr-privacy-history-chevron"
                  style={{ transform: historyOpen ? 'rotate(180deg)' : 'none' }}
                >
                  <polyline points="6 9 12 15 18 9" />
                </svg>
              </span>
            </button>
            {historyOpen && (
              <div className="pr-privacy-history-list">
                {privacyRequests.map((req) => (
                  <div className="pr-privacy-history-item" key={req.request_id}>
                    <div className="pr-privacy-history-body">
                      <div className="pr-privacy-history-label">
                        {TYPE_LABELS[req.request_type] ?? req.request_type}
                      </div>
                      <div className="pr-privacy-history-date">
                        Submitted {fmtDate(req.requested_at ?? req.created_at)}
                      </div>
                    </div>
                    <span className={`pr-privacy-badge ${req.status}`}>
                      {req.status.replace('_', ' ')}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* ── Account ── */}
      <div className="pr-sec-head stagger d5">
        <h3 className="pr-sec-title">Account</h3>
        <span className="pr-sec-sub">Session &amp; data.</span>
      </div>

      <div className="pr-card stagger d5">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div className="pr-settings-info">
            <span className="pr-settings-title">Sign out</span>
            <span className="pr-settings-desc">End this session and return to a fresh start</span>
          </div>
          {/* Was onClick={() => showToast('Signing out...')} -- a toast and
              nothing else. No request, no token cleared, still signed in. */}
          <button
            className="pr-row-btn"
            onClick={handleSignOut}
            type="button"
            disabled={signingOut}
            style={{ fontWeight: 650 }}
          >
            {signingOut ? 'Signing out…' : 'Sign out'}
          </button>
        </div>
      </div>

      {/* Danger Zone */}
      <div className="pr-danger-card stagger d5">
        <div className="pr-danger-head">
          <svg viewBox="0 0 24 24">
            <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
            <line x1="12" y1="9" x2="12" y2="13" />
            <line x1="12" y1="17" x2="12.01" y2="17" />
          </svg>
          Danger Zone
        </div>
        <div className="pr-danger-row">
          <div className="pr-danger-info">
            <span className="pr-danger-title">Delete account</span>
            <span className="pr-danger-desc">Permanently erase your founder profile and all diagnosis data.</span>
          </div>
          <button
            className="pr-danger-btn"
            /* Was 'withdraw_consent': clicking "Delete account" and confirming
               opened the withdraw-consent dialog and POSTed /privacy/withdraw,
               so the account was never scheduled for erasure — while the user
               was told it had been. */
            onClick={() => openAction(PRIVACY_ACTIONS.find(a => a.type === 'delete_account'))}
            type="button"
            id="delete-account-btn"
          >
            Delete account
          </button>
        </div>
      </div>
    </div>
  );
}
