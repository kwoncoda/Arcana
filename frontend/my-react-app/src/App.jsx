import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';

// 레이아웃 및 페이지 컴포넌트 임포트
import AuthLayout from './components/AuthLayout';
import LoginPage from './components/LoginPage';
import RegisterPage from './components/RegisterPage';
import MainDashboard from './components/MainDashboard';
import NotionConnectPage from './components/NotionConnectPage';
import NotionOAuthCallback from './components/NotionOAuthCallback';
// 1. 
// import GoogleOAuthCallback from './components/GoogleOAuthCallback'; 
import MyPage from './components/MyPage';

function App() {
  return (
    <Routes>
      {/* 로그인, 회원가입, 연동 '시작' 페이지만 중앙 정렬 */}
      <Route element={<AuthLayout />}>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/connect/notion" element={<NotionConnectPage />} />
        <Route path="/mypage" element={<MyPage />} />
      </Route>
      
      {/* 대시보드는 전체 화면 */}
      <Route path="/dashboard" element={<MainDashboard />} />
      
      {/* OAuth 콜백 페이지들은 레이아웃이 없는 독립 페이지 */}
      <Route 
        path="/notion/oauth/callback" 
        element={<NotionOAuthCallback />} 
      />
      {/* 2. 
      <Route 
        path="/google-drive/oauth/callback" 
        element={<GoogleOAuthCallback />} 
      />
      */}
      
      {/* 기본 및 예외 경로 */}
      <Route path="/" element={<Navigate to="/login" replace />} />
      <Route path="*" element={<Navigate to="/login" replace />} />
    </Routes>
  );
}

export default App;