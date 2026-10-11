import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
const backend = process.env.VOLTMIND_BACKEND_URL || 'http://127.0.0.1:8080'

export default defineConfig({
  plugins: [react()],
  server: { host: '127.0.0.1', port: 5173, strictPort: true, proxy: { '/api': { target: backend, changeOrigin: false, timeout: 0, proxyTimeout: 0 } } },
  preview: { host: '127.0.0.1', port: 5173, strictPort: true, proxy: { '/api': { target: backend, changeOrigin: false } } },
})
