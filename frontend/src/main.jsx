import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { AppProvider } from './context/AppContext';
import ErrorBoundary from './components/ErrorBoundary';
import App from './App';
import './index.css';
import './styles/onboarding-supplement.css';
import './styles/animations.css';
import './styles/tour.css';

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
