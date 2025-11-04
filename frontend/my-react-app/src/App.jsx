import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import styled from 'styled-components';

// 레이아웃 및 페이지 컴포넌트 임포트
import AuthLayout from './components/AuthLayout';
import LoginPage from './components/LoginPage';
import RegisterPage from './components/RegisterPage';
import MainDashboard from './components/MainDashboard';
import NotionConnectPage from './components/NotionConnectPage';
// 1. 새로 만들 OAuth 콜백 페이지를 임포트합니다.
import NotionOAuthCallback from './components/NotionOAuthCallback';

function App() {
  return (
    <Routes>
      {/* 로그인, 회원가입, 연동 페이지는 중앙 정렬 레이아웃을 사용합니다. */}
      <Route element={<AuthLayout />}>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/connect/notion" element={<NotionConnectPage />} />
        {/* 2. /notion/oauth/callback 경로를 추가합니다. */}
        <Route path="/notion/oauth/callback" element={<NotionOAuthCallback />} />
      </Route>
      
      {/* 대시보드는 전체 화면 레이아웃을 사용합니다. */}
      <Route path="/dashboard" element={<MainDashboard />} />
      
      {/* 기본 경로는 /login으로 리다이렉트합니다. */}
      <Route path="/" element={<Navigate to="/login" replace />} />
      
      {/* 일치하는 경로가 없으면 /login으로 리다이렉트합니다. */}
      <Route path="*" element={<Navigate to="/login" replace />} />
    </Routes>
  );
}

export default App;
