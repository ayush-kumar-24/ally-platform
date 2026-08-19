import { useState, useEffect, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useApp } from '../context/AppContext';
import { get, post } from '../services/api';
import { getProfile, getProgress, updateProfile } from '../services/profile';
import { getNotificationPreferences, updateNotificationPreferences } from '../services/settings';
import { logout } from '../services/auth';
import { getCatalog, getMyPlan } from '../services/plans';
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
    desc: 'Get a full export (JSON) of all data Ally holds about you — founder profile, sessions, and diagnosis history.',
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
    desc: 'See a category-by-category count of what personal and business data Ally currently holds for your account.',
    icon: (
      <svg viewBox="0 0 24 24">
        <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
        <circle cx="12" cy="12" r="3" />
      </svg>
    ),
    confirmTitle: 'View your data summary?',
    confirmDesc: 'Ally will count what\'s held under your account, by category, and download it now.',
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
    confirmDesc: 'Our team will review and correct the identified data within 30 days. Please add details in the request.',
    confirmColor: '#4338ca',
    confirmBg: '#f0f4ff',
  },
  {
    type: 'portability',
    kind: 'export',
    label: 'Export for portability',
    desc: 'Download a machine-readable copy of your data in a portable format (JSON/CSV) to take to another service.',
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
  const planLabel = plan?.plan_name ? `Ally ${plan.plan_name}` : 'Ally Free';
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
  // Ref, not state: state updates are async, so two clicks in the same tick would
  // both see submitting === false. The ref flips synchronously.
  const inFlight = useRef(false);

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
    inFlight.current = true;
    setSubmitting(true);

    const label = TYPE_LABELS[pendingAction.type] ?? pendingAction.label;
    try {
      switch (pendingAction.kind) {
        case 'export': {
          setProgress('Assembling your data…');
          const bundle = await exportData();
          setProgress('Preparing download…');
          downloadExport(bundle, `ally-data-export-${new Date().toISOString().slice(0, 10)}.json`);
          setPrivacyRequests(prev => [bundle.request, ...prev]);
          showToast(`Export ready — ${bundle.record_count} records downloaded ✓`);
          break;
        }
        case 'summary': {
          setProgress('Counting your data…');
          const summary = await getDataSummary();
          setProgress('Preparing download…');
          downloadExport(summary, `ally-data-summary-${new Date().toISOString().slice(0, 10)}.json`);
          setPrivacyRequests(prev => [summary.request, ...prev]);
          showToast(`Summary ready — ${summary.total_records} records across ${Object.keys(summary.counts).length} categories ✓`);
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
          break;
        }
        default: {
          // Rights that need a human to action — queued for review.
          setProgress('Submitting request…');
          const created = await post('/settings/privacy', { request_type: pendingAction.type });
          setPrivacyRequests(prev => [created, ...prev]);
          showToast(`${label} request submitted ✓`);
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
    }
  }, [pendingAction, showToast]);

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
    name: '', email: '', linkedin: '',
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
    reducedMotion: 'reduced_motion',
    privateMode: 'private_mode',
  };
  const [switches, setSwitches] = useState({
    renewal: true,
    notifications: true,
    reducedMotion: false,
    privateMode: true
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
          reducedMotion: prefs.reduced_motion ?? false,
          privateMode: prefs.private_mode ?? true,
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
    try {
      await updateNotificationPreferences({ [SWITCH_FIELD[key]]: next });
    } catch (err) {
      setSwitches(prev => ({ ...prev, [key]: !next }));
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
                  : (['export', 'summary'].includes(pendingAction.kind) ? 'Download now' : 'Confirm')}
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

          <div className="pr-field">
            <div className="pr-lbl">Email</div>
            {/* Email comes from the Google/LinkedIn identity, so it is not editable
                here -- offering an input implied a change we cannot persist. */}
            <div className="pr-val">{form.email || '—'}</div>
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
                AI Chat with Ally
              </div>
              <span className="pr-usage-val">
                {plan ? `${plan.daily_tokens_used ?? 0} / ${plan.daily_token_limit ?? 0} today` : '— / —'}
              </span>
            </div>
            <div className="pr-usage-track">
              <div
                className="pr-usage-fill"
                style={{
                  width: plan?.daily_token_limit
                    ? `${Math.min(100, Math.round((plan.daily_tokens_used / plan.daily_token_limit) * 100))}%`
                    : '0%',
                }}
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

        {/* Renewal Reminder Switch Row */}
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
              <div style={{ fontSize: '13px', fontWeight: 650, color: 'var(--ink, #16241c)' }}>Renewal reminder</div>
              <div style={{ fontSize: '11px', color: 'var(--muted-2)', marginTop: '2px' }}>
                Get notified about new features and offers
              </div>
            </div>
          </div>
          <button
            className={`pr-switch${switches.renewal ? ' on' : ''}`}
            onClick={() => toggleSwitch('renewal')}
            type="button"
          />
        </div>
      </div>

      {/* ── Preferences ── */}
      <div className="pr-sec-head stagger d4">
        <h3 className="pr-sec-title">Preferences</h3>
        <span className="pr-sec-sub">How the workspace behaves.</span>
      </div>

      <div className="pr-card stagger d4">
        <div className="pr-settings-row">
          <div className="pr-settings-info">
            <span className="pr-settings-title">Notifications</span>
            <span className="pr-settings-desc">Report updates, replies and reminders</span>
          </div>
          <button
            className={`pr-switch${switches.notifications ? ' on' : ''}`}
            onClick={() => toggleSwitch('notifications')}
            type="button"
          />
        </div>

        <div className="pr-settings-row">
          <div className="pr-settings-info">
            <span className="pr-settings-title">Reduced motion</span>
            <span className="pr-settings-desc">Minimise animations across the workspace</span>
          </div>
          <button
            className={`pr-switch${switches.reducedMotion ? ' on' : ''}`}
            onClick={() => toggleSwitch('reducedMotion')}
            type="button"
          />
        </div>

        <div className="pr-settings-row">
          <div className="pr-settings-info">
            <span className="pr-settings-title">Private mode</span>
            <span className="pr-settings-desc">Keep business data anonymised in aggregate insights</span>
          </div>
          <button
            className={`pr-switch${switches.privateMode ? ' on' : ''}`}
            onClick={() => toggleSwitch('privateMode')}
            type="button"
          />
        </div>

        <div className="pr-settings-row">
          <div className="pr-settings-info">
            <span className="pr-settings-title">Product tour</span>
            <span className="pr-settings-desc">Replay the 60-second guided walkthrough of Ally</span>
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
        <span className="pr-sec-sub">Your data rights under DPDP &amp; GDPR — requests are reviewed within 30 days.</span>
      </div>

      <div className="pr-card stagger d5">
        {/* Current standing — only rendered when something is actually in effect,
            so the common case stays uncluttered. */}
        {privacyState?.deletion_pending && (
          <div className="pr-privacy-banner" role="status" style={{
            background: '#fff1f2', border: '1px solid #fecdd3', borderRadius: 10,
            padding: '12px 14px', marginBottom: 14, color: '#991b1b', fontSize: 13,
          }}>
            <strong>Account deletion scheduled.</strong>{' '}
            Your data will be erased on {fmtDate(privacyState.deletion_scheduled_at)}. Contact
            support before then to cancel.
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
              onClick={() => setPendingAction(action)}
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
                : ['export', 'summary'].includes(action.kind) ? 'Download'
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
            onClick={() => setPendingAction(PRIVACY_ACTIONS.find(a => a.type === 'delete_account'))}
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
