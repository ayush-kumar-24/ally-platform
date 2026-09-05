import { useState, useEffect, useRef } from 'react';
import { triggerTrackingScripts } from '../utils/cookieUtils';

export default function CookieBanner() {
  const [isOpen, setIsOpen] = useState(false);
  const [showCustomize, setShowCustomize] = useState(false);
  const [analytics, setAnalytics] = useState(false);
  const [marketing, setMarketing] = useState(false);
  const cardRef = useRef(null);
  const restoreFocusTo = useRef(null);

  useEffect(() => {
    // 1. Check if user already set their cookie preferences
    const savedConsent = localStorage.getItem('ally_cookie_consent');
    if (savedConsent) {
      try {
        const parsed = JSON.parse(savedConsent);
        // Trigger scripts if consent was previously granted
        triggerTrackingScripts(parsed);
      } catch {
        // Fallback for corrupted data
        setIsOpen(true);
      }
    } else {
      // Show the banner if no preference is saved
      setIsOpen(true);
    }
  }, []);

  /* This renders over every route from App.jsx and blocks the page visually,
     but had none of the behaviour that makes a dialog a dialog: focus stayed
     wherever it was, Tab walked straight out into the page behind, and focus
     was never returned afterwards. A keyboard user could tab the entire site
     underneath a consent gate without ever reaching its buttons.

     Deliberately NO Escape-to-close: silently dismissing a consent gate would
     record no choice at all. The buttons are the only way out. */
  useEffect(() => {
    if (!isOpen) return undefined;
    restoreFocusTo.current = document.activeElement;

    const SELECTOR = 'button:not([disabled]), input:not([disabled]), a[href]';
    const first = cardRef.current?.querySelector(SELECTOR);
    first?.focus();

    const onKeyDown = (e) => {
      if (e.key !== 'Tab' || !cardRef.current) return;
      const items = [...cardRef.current.querySelectorAll(SELECTOR)]
        .filter(el => el.offsetParent !== null);
      if (!items.length) return;
      const firstEl = items[0];
      const lastEl = items[items.length - 1];
      if (e.shiftKey && document.activeElement === firstEl) {
        e.preventDefault();
        lastEl.focus();
      } else if (!e.shiftKey && document.activeElement === lastEl) {
        e.preventDefault();
        firstEl.focus();
      }
    };

    document.addEventListener('keydown', onKeyDown);
    return () => {
      document.removeEventListener('keydown', onKeyDown);
      if (restoreFocusTo.current instanceof HTMLElement) restoreFocusTo.current.focus();
    };
  }, [isOpen]);

  const savePreferences = (preferences) => {
    localStorage.setItem('ally_cookie_consent', JSON.stringify(preferences));
    triggerTrackingScripts(preferences);
    setIsOpen(false);
  };

  const handleAcceptAll = () => {
    const preferences = {
      cookie_consent: true,
      functional: true,
      analytics: true,
      marketing: true,
    };
    savePreferences(preferences);
  };

  const handleRejectNonEssential = () => {
    const preferences = {
      cookie_consent: true,
      functional: true,
      analytics: false,
      marketing: false,
    };
    savePreferences(preferences);
  };

  const handleSaveCustomized = () => {
    const preferences = {
      cookie_consent: true,
      functional: true,
      analytics: analytics,
      marketing: marketing,
    };
    savePreferences(preferences);
  };

  if (!isOpen) return null;

  return (
    <div
      className="cookie-banner-overlay"
      role="dialog"
      aria-modal="true"
      aria-labelledby="cookie-banner-title"
      aria-describedby="cookie-banner-desc"
    >
      {/* `is-customizing` lets the stylesheet give the toggles a full-width
          column; the closed bar is a single compact row on desktop. */}
      <div className={`cookie-banner-card${showCustomize ? ' is-customizing' : ''}`} ref={cardRef}>
        <div className="cookie-banner-header">
          <div className="cookie-banner-icon-wrapper">
            <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" strokeWidth="2" className="text-emerald">
              <path d="M12 2a10 10 0 1 0 10 10 4 4 0 0 1-5-5 4 4 0 0 1-5-5Z" />
              <path d="M12 10a1 1 0 1 0 0-2 1 1 0 0 0 0 2ZM8 14a1 1 0 1 0 0-2 1 1 0 0 0 0 2ZM16 15a1 1 0 1 0 0-2 1 1 0 0 0 0 2ZM12 18a1 1 0 1 0 0-2 1 1 0 0 0 0 2Z" />
            </svg>
          </div>
          <div className="cookie-banner-title-area">
            <h3 id="cookie-banner-title">We value your privacy</h3>
            <p className="cookie-banner-desc" id="cookie-banner-desc">
              We use cookies to enhance your experience, analyze site usage, and support our marketing efforts. By default, non-essential cookies are blocked.
            </p>
          </div>
        </div>

        {showCustomize && (
          <div className="cookie-customize-panel" id="cookie-customize-panel">
            <div className="cookie-option">
              <div className="cookie-option-info">
                <span className="cookie-option-name">Essential Cookies</span>
                <span className="cookie-option-desc">Necessary for the platform to function. Cannot be disabled.</span>
              </div>
              {/* The label wraps only the visual slider span — the visible name
                  sits in a sibling div — so without aria-label all three of
                  these announced as a bare "checkbox" on a consent surface. */}
              <label className="cookie-switch disabled">
                <input type="checkbox" checked disabled readOnly aria-label="Essential cookies (always on)" />
                <span className="cookie-slider" aria-hidden="true"></span>
              </label>
            </div>

            <div className="cookie-option">
              <div className="cookie-option-info">
                <span className="cookie-option-name">Performance & Analytics</span>
                <span className="cookie-option-desc">Help us understand how visitors interact with the platform.</span>
              </div>
              <label className="cookie-switch">
                <input
                  type="checkbox"
                  aria-label="Performance and analytics cookies"
                  checked={analytics}
                  onChange={(e) => setAnalytics(e.target.checked)}
                />
                <span className="cookie-slider" aria-hidden="true"></span>
              </label>
            </div>

            <div className="cookie-option">
              <div className="cookie-option-info">
                <span className="cookie-option-name">Marketing & Advertising</span>
                <span className="cookie-option-desc">Used to deliver relevant advertisements and track campaigns.</span>
              </div>
              <label className="cookie-switch">
                <input
                  type="checkbox"
                  aria-label="Marketing and advertising cookies"
                  checked={marketing}
                  onChange={(e) => setMarketing(e.target.checked)}
                />
                <span className="cookie-slider" aria-hidden="true"></span>
              </label>
            </div>
          </div>
        )}

        <div className="cookie-banner-actions">
          <div className="cookie-banner-left-actions">
            <button
              className="cookie-btn cookie-btn-link"
              onClick={() => setShowCustomize(!showCustomize)}
              type="button"
              aria-expanded={showCustomize}
              aria-controls="cookie-customize-panel"
            >
              {showCustomize ? 'Hide Customization' : 'Customize Preferences'}
            </button>
          </div>
          <div className="cookie-banner-right-actions">
            {showCustomize ? (
              <button 
                className="cookie-btn cookie-btn-emerald" 
                onClick={handleSaveCustomized}
                type="button"
              >
                Save Preferences
              </button>
            ) : (
              <>
                <button 
                  className="cookie-btn cookie-btn-outline" 
                  onClick={handleRejectNonEssential}
                  type="button"
                >
                  Reject Non-Essential
                </button>
                <button 
                  className="cookie-btn cookie-btn-emerald" 
                  onClick={handleAcceptAll}
                  type="button"
                >
                  Accept All
                </button>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
