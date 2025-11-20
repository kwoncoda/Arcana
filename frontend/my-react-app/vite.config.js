import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    allowedHosts: ['arcana.it.kr'],
    proxy: {
      // '/api'로 시작하는 요청을 감지합니다.
      '/api': {
        // 실제 백엔드 서버 주소로 변경해주세요.
        target: 'http://arcana-backend:8000', 
        changeOrigin: true
      },
    },
  },
})