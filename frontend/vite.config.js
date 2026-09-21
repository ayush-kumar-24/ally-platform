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

/**
 * Stamp the chunk-to-chunk import specifiers too.
 *
 * `renderBuiltUrl` below does NOT reach these, and that gap is the whole
 * reason this plugin exists. Vite routes ASSET references through it -- the
 * <script> in index.html, url() in CSS, and the preload list inside
 * __vite__mapDeps -- but the ES module specifier that actually fetches a lazy
 * chunk is emitted by Rollup as a plain relative path and never passes
 * through. A production build therefore came out mixed:
 *
 *     <script src="/assets/index-Cyqje68V.js?dpl=dpl_8FePn...">   stamped
 *     import("./PlatformLayout-DfhBTNec.js")                       NOT stamped
 *
 * which is exactly what a founder's crash report showed. Two consequences,
 * both bad:
 *
 * 1. SKEW. The stamp is what pins a request to the deployment the tab was
 *    loaded from. Unstamped, every lazily-loaded chunk is served by whatever
 *    deployment is CURRENT instead -- so a tab opened before a deploy runs
 *    the old entry bundle and then pulls new chunks into it. Two builds in
 *    one page, which breaks in whatever way their differences happen to
 *    break. The entry point was pinned and everything behind it was not,
 *    which is close to the worst of both: the failure only appears after a
 *    deploy, on pages a founder had already opened.
 *
 * 2. DOUBLE FETCH. The preload says /assets/X.js?dpl=... and the import says
 *    ./X.js. Different URLs, so the browser never matches them up: the
 *    modulepreload is wasted and the chunk is fetched a second time. Every
 *    lazy chunk, every navigation.
 *
 * Rewriting is deliberately conservative: a specifier is only touched when
 * the file it names is actually a chunk in this bundle. The names carry a
 * content hash, so matching one by accident inside unrelated string data is
 * not a realistic risk, and anything already stamped cannot match (the
 * pattern requires the closing quote immediately after `.js`).
 *
 * generateBundle rather than renderChunk: every filename is final by then, so
 * the set of real chunk names is exact. No sourcemaps are emitted in this
 * build, so editing the code here invalidates nothing.
 */
function stampChunkImports(id) {
  return {
    name: 'ally-stamp-chunk-imports',
    enforce: 'post',
    generateBundle(_options, bundle) {
      const chunkNames = new Set(
        Object.keys(bundle)
          .filter((file) => file.endsWith('.js'))
          .map((file) => file.split('/').pop()),
      )
      let stamped = 0
      for (const file of Object.values(bundle)) {
        if (file.type !== 'chunk') continue
        file.code = file.code.replace(
          /(["'`])(\.{1,2}\/)([A-Za-z0-9_.-]+\.js)\1/g,
          (whole, quote, prefix, name) => {
            if (!chunkNames.has(name)) return whole
            stamped += 1
            return `${quote}${prefix}${name}?dpl=${id}${quote}`
          },
        )
      }
      this.info(`stamped ${stamped} chunk import specifiers with ?dpl=${id}`)
    },
  }
}

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
    // Only when Vercel gives us a deployment id -- same condition as the
    // `experimental` block below, so a local build stays byte-for-byte what
    // it is today.
    ...(deploymentId ? [stampChunkImports(deploymentId)] : []),
  ],
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
