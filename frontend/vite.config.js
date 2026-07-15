import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    strictPort: false,
    proxy: {
      '/ws': { target: 'ws://localhost:8001', ws: true },
      '/api': { target: 'http://localhost:8001' },
    }
  }
})
