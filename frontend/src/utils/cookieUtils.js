/**
 * Tracking scripts loaded inside the SIGNED-IN product, on consent.
 *
 * NO ADVERTISING TAG IS LOADED FROM HERE, AND THAT IS THE POINT.
 *
 * The Privacy Policy says, in terms: "We do not use your personal data for
 * targeted advertising." This file used to inject the Meta (Facebook) Pixel
 * whenever a founder accepted marketing cookies, which would have made that
 * sentence untrue the moment a pixel ID was configured. Nothing was firing --
 * the deploy workflow never passes VITE_META_PIXEL_ID, so the injector
 * returned early -- but "the secret happens not to be set" is not a privacy
 * control. Adding one line to a workflow file would have switched on ad
 * tracking inside the pages that hold founders' diagnostic answers, with no
 * review and no change to the policy.
 *
 * Marketing tags belong on the public landing site, which is a separate
 * codebase with its own consent banner and its own policy. That was already
 * the stated plan; this file simply no longer contradicts it.
 *
 * The banner still RECORDS a marketing preference, and should: the choice is
 * part of the consent record either way, and dropping it would lose the
 * history. It just no longer causes anything to load here.
 */

// Simple flag to prevent duplicate injection
let isAnalyticsInitialized = false;

/**
 * Injects Google Analytics tracking script.
 *
 * Only when a real measurement ID is configured. The previous default was a
 * placeholder, which meant every founder who accepted cookies had their
 * browser call Google with a fake ID from inside the diagnosis -- noise for
 * us, and a third-party request from pages that hold private answers. With
 * nothing configured, consent is recorded and nothing loads.
 */
export function initializeAnalytics(measurementId = import.meta.env.VITE_GA_MEASUREMENT_ID) {
  if (!measurementId) return;
  if (isAnalyticsInitialized) return;
  if (window.gtag) {
    isAnalyticsInitialized = true;
    return;
  }

  try {
    // 1. Inject the external gtag script
    const script = document.createElement('script');
    script.async = true;
    script.src = `https://www.googletagmanager.com/gtag/js?id=${measurementId}`;
    document.head.appendChild(script);

    // 2. Setup the global dataLayer and gtag function
    window.dataLayer = window.dataLayer || [];
    window.gtag = function gtag() {
      window.dataLayer.push(arguments);
    };

    // 3. Configure/initialize
    window.gtag('js', new Date());
    window.gtag('config', measurementId, {
      anonymize_ip: true, // compliance setting
      cookie_flags: 'SameSite=None;Secure'
    });

    isAnalyticsInitialized = true;
    if (import.meta.env.DEV) console.debug('[Consent] Google Analytics initialized.');
  } catch (error) {
    console.error('[Consent] Failed to load Google Analytics:', error);
  }
}

/**
 * Loads what the founder's choice permits. Analytics only -- see the note at
 * the top of this file for why `consents.marketing` deliberately loads nothing.
 *
 * @param {Object} consents - Cookie preferences
 */
export function triggerTrackingScripts(consents) {
  if (!consents) return;

  if (consents.analytics) {
    initializeAnalytics();
  }
}
