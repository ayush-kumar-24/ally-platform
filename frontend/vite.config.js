import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

/* Version-stamp every built asset so a tab opened before a deploy can still
   fetch the chunks it is holding names for.
 *
 * This is the CURE for the stale-chunk error card (utils/loadChunk.js and
 * ErrorBoundary handle the symptom). The app is code-split, chunk file names
 * carry a content hash, and the moment a new build goes live the old names
 * stop resolving -- so a founder who opened onboarding before the deploy and
 * clicks "Continue" after it asks for a file that no longer exists.
 *
 * With `?dpl=<deployment id>` on every asset URL and Vercel's Skew Protection
 * enabled, Vercel routes that request back to the deployment it came from, and
 * the old chunk is still served. The tab finishes its session on the build it
 * started on; the next full page load picks up the new one.
 *
 * IMPORTANT: this only takes effect once Skew Protection is switched on for
 * the project (Vercel -> Project -> Settings -> Advanced). That toggle is also
 * what exposes VERCEL_DEPLOYMENT_ID to the build -- so until it is on, the
 * variable is absent, `experimental` stays undefined, and the build is byte-
 * for-byte what it is today. Landing this ahead of the toggle is safe; it just
 * does nothing yet.
 */
const deploymentId = process.env.VERCEL_DEPLOYMENT_ID

export default defineConfig({
  plugins: [react(), tailwindcss()],
  ...(deploymentId
    ? {
        experimental: {
          // `filename` is the asset's path inside dist ("assets/Foo-a1b2.js").
          // An absolute URL is correct here because base is "/" -- and it has
          // to be absolute, since the same stamped URL is emitted into CSS and
          // into nested chunks, which resolve relative paths differently.
          renderBuiltUrl(filename) {
            return `/${filename}?dpl=${deploymentId}`
          },
        },
      }
    : {}),
  server: {
    // Proxy API calls to the FastAPI backend so the browser talks same-origin
    // (no CORS in dev). With this, VITE_API_URL can be the relative "/api/v1".
    proxy: {
      // Target is env-driven so the port can move without editing this file
      // (port 8000 is taken by another local project on some machines).
      //
      // 127.0.0.1 rather than localhost, deliberately. Node 18+ resolves
      // localhost to ::1 first, uvicorn binds IPv4 only unless told otherwise,
      // and the proxy then answers every /api call with a 502 that looks like
      // the backend is down when it is running perfectly.
      '/api': {
        target: process.env.VITE_BACKEND_URL || 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
})
