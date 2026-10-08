import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { resolve } from 'node:path'

export default defineConfig({
  plugins: [react()],
  base: process.env.PRODUCT_BASE ?? '/product/',
  build: {
    manifest: true,
    rollupOptions: {
      input: resolve(__dirname, 'index.html'),
      output: {
        manualChunks(id) {
          if (
            id.includes('/node_modules/react/')
            || id.includes('/node_modules/react-dom/')
            || id.includes('/node_modules/scheduler/')
          ) return 'react-core'
          return undefined
        },
      },
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': process.env.SECFUSION_API_PROXY ?? 'http://127.0.0.1:8001',
      '/health': process.env.SECFUSION_API_PROXY ?? 'http://127.0.0.1:8001',
    },
  },
})
