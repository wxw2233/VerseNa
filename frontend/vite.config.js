import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    host: '127.0.0.1',
    port: 5173,
    strictPort: false,
    proxy: {
      '/ws': { target: 'ws://localhost:8002', ws: true },
      '/api': { target: 'http://localhost:8002' },
    }
  }
})
