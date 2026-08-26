// Vite 构建配置
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173, // 前端开发服务器端口
    // 本地开发代理：/api 转发到后端（8000），避免 CORS
    proxy: {
      '/api': { target: 'http://127.0.0.1:8000', changeOrigin: true },
    },
  },
  build: {
    outDir: 'dist',
    chunkSizeWarningLimit: 1200, // element-plus 体积较大，调高告警阈值
  },
})
