import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    // Proxy API calls to the FastAPI backend so the browser talks same-origin
    // (no CORS in dev). With this, VITE_API_URL can be the relative "/api/v1".
    proxy: {
      '/api': { target: 'http://localhost:8000', changeOrigin: true },
    },
  },
})
