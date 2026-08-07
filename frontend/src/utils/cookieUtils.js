/**
 * Dynamic tracking script injector based on user cookie consents
 */

// Simple flag to prevent duplicate injection
let isAnalyticsInitialized = false;
let isMarketingInitialized = false;

/**
 * Injects Google Analytics tracking script
 * Uses a placeholder GTM ID if not configured.
 */
export function initializeAnalytics(measurementId = 'G-MOCKTRACKINGID') {
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
 * Injects Meta Pixel (Facebook Pixel) tracking script
 */
export function initializeMarketing(pixelId = 'MOCK_PIXEL_ID') {
  if (isMarketingInitialized) return;
  if (window.fbq) {
    isMarketingInitialized = true;
    return;
  }

  try {
    /* Meta's own snippet, de-minified. Functionally identical to the copy-paste
       version — the original relied on a leading `!` and a bare ternary as
       statements, which are expressions evaluated purely for side effects. */
    const src = 'https://connect.facebook.net/en_US/fbevents.js';
    if (!window.fbq) {
      const fbq = function (...args) {
        if (fbq.callMethod) fbq.callMethod.apply(fbq, args);
        else fbq.queue.push(args);
      };
      fbq.push = fbq;
      fbq.loaded = true;
      fbq.version = '2.0';
      fbq.queue = [];
      window.fbq = fbq;
      if (!window._fbq) window._fbq = fbq;

      const script = document.createElement('script');
      script.async = true;
      script.src = src;
      const first = document.getElementsByTagName('script')[0];
      first.parentNode.insertBefore(script, first);
    }

    window.fbq('init', pixelId);
    window.fbq('track', 'PageView');

    isMarketingInitialized = true;
    if (import.meta.env.DEV) console.debug('[Consent] Meta Pixel initialized.');
  } catch (error) {
    console.error('[Consent] Failed to load Meta Pixel:', error);
  }
}

/**
 * Evaluates preferences and injects scripts accordingly
 * @param {Object} consents - Cookie preferences
 */
export function triggerTrackingScripts(consents) {
  if (!consents) return;

  if (consents.analytics) {
    initializeAnalytics();
  }

  if (consents.marketing) {
    initializeMarketing();
  }
}
