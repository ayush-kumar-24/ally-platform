import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
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
