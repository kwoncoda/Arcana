import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      // '/api'로 시작하는 요청을 감지합니다.
      '/api': {
        // 실제 백엔드 서버 주소로 변경해주세요.
        target: 'http://localhost:8000', 
        changeOrigin: true
      },
    },
  },
})