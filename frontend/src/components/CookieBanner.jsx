import { useState, useEffect } from 'react';
import { triggerTrackingScripts } from '../utils/cookieUtils';

export default function CookieBanner() {
  const [isOpen, setIsOpen] = useState(false);
  const [showCustomize, setShowCustomize] = useState(false);
  const [analytics, setAnalytics] = useState(false);
  const [marketing, setMarketing] = useState(false);

  useEffect(() => {
    // 1. Check if user already set their cookie preferences
    const savedConsent = localStorage.getItem('ally_cookie_consent');
    if (savedConsent) {
      try {
        const parsed = JSON.parse(savedConsent);
        // Trigger scripts if consent was previously granted
        triggerTrackingScripts(parsed);
      } catch (e) {
        // Fallback for corrupted data
        setIsOpen(true);
      }
    } else {
      // Show the banner if no preference is saved
      setIsOpen(true);
    }
  }, []);

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
    <div className="cookie-banner-overlay" role="dialog" aria-labelledby="cookie-banner-title">
      <div className="cookie-banner-card">
        <div className="cookie-banner-header">
          <div className="cookie-banner-icon-wrapper">
            <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" strokeWidth="2" className="text-emerald">
              <path d="M12 2a10 10 0 1 0 10 10 4 4 0 0 1-5-5 4 4 0 0 1-5-5Z" />
              <path d="M12 10a1 1 0 1 0 0-2 1 1 0 0 0 0 2ZM8 14a1 1 0 1 0 0-2 1 1 0 0 0 0 2ZM16 15a1 1 0 1 0 0-2 1 1 0 0 0 0 2ZM12 18a1 1 0 1 0 0-2 1 1 0 0 0 0 2Z" />
            </svg>
          </div>
          <div className="cookie-banner-title-area">
            <h3 id="cookie-banner-title">We value your privacy</h3>
            <p className="cookie-banner-desc">
              We use cookies to enhance your experience, analyze site usage, and support our marketing efforts. By default, non-essential cookies are blocked.
            </p>
          </div>
        </div>

        {showCustomize && (
          <div className="cookie-customize-panel">
            <div className="cookie-option">
              <div className="cookie-option-info">
                <span className="cookie-option-name">Essential Cookies</span>
                <span className="cookie-option-desc">Necessary for the platform to function. Cannot be disabled.</span>
              </div>
              <label className="cookie-switch disabled">
                <input type="checkbox" checked disabled />
                <span className="cookie-slider"></span>
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
                  checked={analytics} 
                  onChange={(e) => setAnalytics(e.target.checked)} 
                />
                <span className="cookie-slider"></span>
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
                  checked={marketing} 
                  onChange={(e) => setMarketing(e.target.checked)} 
                />
                <span className="cookie-slider"></span>
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
