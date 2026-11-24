import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

const django = { target: 'http://127.0.0.1:8000', changeOrigin: false }

export default defineConfig({
  base: './',
  plugins: [vue()],
  server: {
    proxy: {
      '/api/': django,
      '/admin/': django,
      '/static/': django,
    },
  },
})
