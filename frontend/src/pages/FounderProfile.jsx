import { useState, useRef, useEffect } from 'react';
import { useApp } from '../context/AppContext';

export default function FounderProfile() {
  const { user, setUser, showToast } = useApp();
  const [editing, setEditing] = useState(false);

  // Form Fields
  const [form, setForm] = useState({
    name: 'Ayush Sharma',
    email: 'ayush@brightloom.in',
    phone: '+91 98765 43210',
    linkedin: 'linkedin.com/in/ayush-sharma',
    location: 'Bengaluru, India'
  });

  // Preferences Switches
  const [switches, setSwitches] = useState({
    renewal: true,
    notifications: true,
    reducedMotion: false,
    privateMode: true
  });

  const toggleSwitch = (key) => {
    setSwitches(prev => ({ ...prev, [key]: !prev[key] }));
  };

  const handleSave = () => {
    setEditing(false);
    setUser(prev => ({
      ...prev,
      name: form.name,
      location: form.location
    }));
    showToast('Profile settings saved ✓');
  };

  return (
    <div className="dc-container">
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
                background: 'linear-gradient(135deg, #34d399, #A8D94A)',
                boxShadow: '0 0 0 3px rgba(255,255,255,0.08), 0 8px 24px -6px rgba(0,0,0,0.5)'
              }}
            >
              AS
            </div>
            <button
              className="fp-cam"
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
                color: '#34d399',
                cursor: 'pointer'
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
            <div style={{ fontSize: '13.5px', color: 'var(--on-dark-muted)', marginBottom: '10px' }}>
              Founder & CEO - BrightLoom
            </div>
            <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
              <span className="fp-hchip" style={{ fontSize: '11px', padding: '4px 9px' }}>
                <svg viewBox="0 0 24 24" style={{ width: 12, height: 12, fill: 'none', stroke: '#34d399', strokeWidth: 2, marginRight: 4 }}>
                  <path d="M21 10c0 7-9 13-9 13S3 17 3 10a9 9 0 0 1 18 0z" />
                  <circle cx="12" cy="10" r="3" />
                </svg>
                {form.location}
              </span>
              <span className="fp-hchip" style={{ fontSize: '11px', padding: '4px 9px' }}>
                <svg viewBox="0 0 24 24" style={{ width: 12, height: 12, fill: 'none', stroke: '#34d399', strokeWidth: 2, marginRight: 4 }}>
                  <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" />
                  <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" />
                </svg>
                1
              </span>
              <span className="fp-hchip" style={{ fontSize: '11px', padding: '4px 9px' }}>
                <svg viewBox="0 0 24 24" style={{ width: 12, height: 12, fill: 'none', stroke: '#34d399', strokeWidth: 2, marginRight: 4 }}>
                  <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
                </svg>
                1
              </span>
            </div>
          </div>
        </div>

        {/* Ring Score */}
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
                style={{ strokeDasharray: 276, strokeDashoffset: 0 }}
              />
            </svg>
            <div className="rep-ring-c">
              <b style={{ fontSize: '20px' }}>100%</b>
              <small style={{ fontSize: '6.5px', letterSpacing: '0.08em', marginTop: '1px' }}>DNA</small>
            </div>
          </div>
          <div className="fd-hero-label" style={{ fontSize: '9px', color: 'var(--on-dark-muted)', maxWidth: '90px', lineHeight: 1.2 }}>
            Founder DNA mapped
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
                type="button"
              >
                Save
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
            <div className="pr-lbl">Full Name</div>
            {editing ? (
              <input
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
            {editing ? (
              <input
                className="pr-input"
                value={form.email}
                onChange={e => setForm({ ...form, email: e.target.value })}
              />
            ) : (
              <div className="pr-val">{form.email}</div>
            )}
          </div>

          <div className="pr-field">
            <div className="pr-lbl">Phone</div>
            {editing ? (
              <input
                className="pr-input"
                value={form.phone}
                onChange={e => setForm({ ...form, phone: e.target.value })}
              />
            ) : (
              <div className="pr-val">{form.phone}</div>
            )}
          </div>

          <div className="pr-field">
            <div className="pr-lbl">Linkedin</div>
            {editing ? (
              <input
                className="pr-input"
                value={form.linkedin}
                onChange={e => setForm({ ...form, linkedin: e.target.value })}
              />
            ) : (
              <div className="pr-val">{form.linkedin}</div>
            )}
          </div>

          <div className="pr-field" style={{ gridColumn: '1 / -1' }}>
            <div className="pr-lbl">Location</div>
            {editing ? (
              <input
                className="pr-input"
                value={form.location}
                onChange={e => setForm({ ...form, location: e.target.value })}
              />
            ) : (
              <div className="pr-val">{form.location}</div>
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
                <b style={{ fontSize: '15px', color: 'var(--forest, #1b4332)' }}>Ally Free</b>
                <span
                  style={{
                    fontSize: '8.5px',
                    fontWeight: 800,
                    letterSpacing: '0.04em',
                    textTransform: 'uppercase',
                    background: '#e2e8f0',
                    color: '#475569',
                    padding: '3px 8px',
                    borderRadius: '4px'
                  }}
                >
                  Free Plan
                </span>
              </div>
              <div style={{ fontSize: '12px', color: 'var(--muted-2)', marginTop: '4px' }}>
                You're on the free plan — upgrade anytime.
              </div>
            </div>
          </div>
          <div style={{ textAlign: 'right' }}>
            <b style={{ fontSize: '20px', color: 'var(--ink, #16241c)', display: 'block', lineHeight: 1 }}>₹0</b>
            <span style={{ fontSize: '10.5px', color: 'var(--muted-2)' }}>forever</span>
          </div>
        </div>

        {/* Upgrade button */}
        <button
          className="btn btn-primary"
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

        {/* Usage statistics header */}
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
          This month's usage
        </div>

        {/* Usage meters list */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', marginBottom: '26px' }}>
          {/* Chat usage */}
          <div className="pr-usage-row">
            <div className="pr-usage-label-row">
              <div className="pr-usage-title">
                <svg viewBox="0 0 24 24">
                  <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
                </svg>
                AI Chat with Ally
              </div>
              <span className="pr-usage-val">18 / 20</span>
            </div>
            <div className="pr-usage-track">
              <div className="pr-usage-fill" style={{ width: '90%' }} />
            </div>
          </div>

          {/* Business diagnosis usage */}
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
              <span className="pr-usage-val">1 / 1</span>
            </div>
            <div className="pr-usage-track">
              <div className="pr-usage-fill" style={{ width: '100%' }} />
            </div>
          </div>

          {/* Document analysis */}
          <div className="pr-usage-row">
            <div className="pr-usage-label-row">
              <div className="pr-usage-title" style={{ color: 'var(--muted-2)' }}>
                <svg viewBox="0 0 24 24">
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                  <polyline points="14 2 14 8 20 8" />
                </svg>
                Document Analysis
              </div>
              <span
                style={{
                  fontSize: '8.5px',
                  fontWeight: 800,
                  letterSpacing: '0.04em',
                  textTransform: 'uppercase',
                  background: '#fef3c7',
                  color: '#d97706',
                  padding: '3px 8px',
                  borderRadius: '4px',
                  border: '1px solid #fde68a'
                }}
              >
                Upgrade to Pro
              </span>
            </div>
            <div className="pr-usage-track" style={{ opacity: 0.5 }} />
          </div>

          {/* Team members usage */}
          <div className="pr-usage-row">
            <div className="pr-usage-label-row">
              <div className="pr-usage-title">
                <svg viewBox="0 0 24 24">
                  <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
                  <circle cx="9" cy="7" r="4" />
                </svg>
                Team Members
              </div>
              <span className="pr-usage-val">1 / 1</span>
            </div>
            <div className="pr-usage-track">
              <div className="pr-usage-fill" style={{ width: '100%' }} />
            </div>
          </div>
        </div>

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
            onClick={() => showToast('Guided tour starting...')}
            type="button"
          >
            <svg viewBox="0 0 24 24">
              <polygon points="5 3 19 12 5 21 5 3" />
            </svg>
            Replay tour
          </button>
        </div>
      </div>

      {/* ── Account ── */}
      <div className="pr-sec-head stagger d5">
        <h3 className="pr-sec-title">Account</h3>
        <span className="pr-sec-sub">Session & data.</span>
      </div>

      <div className="pr-card stagger d5">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div className="pr-settings-info">
            <span className="pr-settings-title">Sign out</span>
            <span className="pr-settings-desc">End this session and return to a fresh start</span>
          </div>
          <button
            className="pr-row-btn"
            onClick={() => showToast('Signing out...')}
            type="button"
            style={{ fontWeight: 650 }}
          >
            Sign out
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
            onClick={() => showToast('Account deletion requested ✓')}
            type="button"
          >
            Delete account
          </button>
        </div>
      </div>
    </div>
  );
}
