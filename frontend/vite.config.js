import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// 构建输出到 dist/，由 FastAPI 在 /ui 提供。
// base 用绝对路径 '/'，配合 api.py 的 /assets 静态挂载。
export default defineConfig({
  plugins: [vue()],
  base: '/',
  build: {
    outDir: 'dist',
    chunkSizeWarningLimit: 1500,
    rollupOptions: {
      output: {
        manualChunks: {
          echarts: ['echarts', 'vue-echarts'],
          naive: ['naive-ui'],
          markdown: ['markdown-it', 'highlight.js', 'katex']
        }
      }
    }
  }
})
