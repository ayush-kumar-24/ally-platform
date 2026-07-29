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
    console.log('[Consent] Google Analytics script initialized.');
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
    // Standard Facebook Pixel integration code
    !(function (f, b, e, v, n, t, s) {
      if (f.fbq) return;
      n = f.fbq = function () {
        n.callMethod ? n.callMethod.apply(n, arguments) : n.queue.push(arguments);
      };
      if (!f._fbq) f._fbq = n;
      n.push = n;
      n.loaded = !0;
      n.version = '2.0';
      n.queue = [];
      t = b.createElement(e);
      t.async = !0;
      t.src = v;
      s = b.getElementsByTagName(e)[0];
      s.parentNode.insertBefore(t, s);
    })(window, document, 'script', 'https://connect.facebook.net/en_US/fbevents.js');

    window.fbq('init', pixelId);
    window.fbq('track', 'PageView');

    isMarketingInitialized = true;
    console.log('[Consent] Meta Pixel script initialized.');
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
