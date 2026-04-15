import { defineConfig } from 'vite'

export default defineConfig({
  base: '/doc-convert/',
  server: {
    proxy: {
      '/doc-convert/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
})
