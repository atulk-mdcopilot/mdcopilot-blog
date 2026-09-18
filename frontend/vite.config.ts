import path from 'node:path'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// Where the dev server forwards /api. In docker compose the backend service is "api".
const apiTarget = process.env.VITE_API_PROXY_TARGET ?? 'http://api:8000'
// Bind-mounted source on Docker Desktop for macOS: inotify events normally arrive,
// but polling is the fallback when HMR does not pick up edits.
const usePolling = process.env.VITE_USE_POLLING === 'true'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(import.meta.dirname, './src'),
    },
  },
  server: {
    host: true,
    port: 5173,
    strictPort: true,
    allowedHosts: ['web', 'localhost'],
    watch: usePolling ? { usePolling: true, interval: 300 } : undefined,
    proxy: {
      '/api': {
        target: apiTarget,
        // false keeps the browser's Host (e.g. localhost:5173) so the backend
        // sees the same Host/Origin pair a production nginx would forward.
        changeOrigin: false,
        xfwd: true,
      },
    },
  },
  preview: {
    host: true,
    port: 4173,
    strictPort: true,
  },
})
