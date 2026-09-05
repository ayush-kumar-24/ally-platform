import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
// Self-hosted variable fonts (replaces the Google Fonts CDN link). Bundled with
// the app so the screen AND the PDF renderer use identical, offline-safe faces.
import '@fontsource-variable/inter';
import '@fontsource-variable/inter/wght-italic.css';       // body <em> emphasis
import '@fontsource-variable/inter-tight';
import '@fontsource-variable/montserrat';
import '@fontsource-variable/fraunces';
import '@fontsource-variable/fraunces/wght-italic.css';    // serif hero <em> italic
import { AppProvider } from './context/AppContext';
import ErrorBoundary from './components/ErrorBoundary';
import { reportError } from './services/errorReporting';
import App from './App';
import './index.css';
import './styles/onboarding-supplement.css';
import './styles/onboarding-questions.css';
import './styles/animations.css';
import './styles/tour.css';
import './styles/help-widget.css';

// ErrorBoundary (below) only catches errors React's render phase throws
// through its own tree -- by design, React error boundaries do NOT catch
// errors from event handlers, timers, or async code/rejected promises. These
// two listeners are what catch that other, larger class of real production
// errors, which would otherwise be invisible even with ErrorBoundary in place.
window.addEventListener('error', (event) => {
  reportError(event.error ?? event.message, { source: 'window_error' });
});
window.addEventListener('unhandledrejection', (event) => {
  reportError(event.reason, { source: 'unhandled_rejection' });
});

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    {/* Root-level catch-all — last resort if all inner boundaries fail */}
    <ErrorBoundary label="Application" fallbackPath="/">
      <BrowserRouter>
        <AppProvider>
          <App />
        </AppProvider>
      </BrowserRouter>
    </ErrorBoundary>
  </React.StrictMode>
);
