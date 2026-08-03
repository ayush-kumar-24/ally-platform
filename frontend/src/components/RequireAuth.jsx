import { Navigate, useLocation } from 'react-router-dom';
import { getAccessToken } from '../services/api';

/**
 * Guards the main platform: no access token, no render.
 *
 * Without this, landing on e.g. /app/diagnosis with no session sent every
 * request with no Authorization header. In dev mode the backend's no-token
 * fallback silently authenticates that as a placeholder founder that doesn't
 * exist in the database, so every call 404s and the page shows a generic
 * "couldn't reach the server" -- which reads as a network glitch, not "you
 * aren't signed in." This catches the missing-session case before any of
 * that happens and sends the founder to login instead.
 */
export default function RequireAuth({ children }) {
  const location = useLocation();
  if (!getAccessToken()) {
    return <Navigate to="/guided/login" replace state={{ from: location.pathname }} />;
  }
  return children;
}
