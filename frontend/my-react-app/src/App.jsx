import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import AuthLayout from './components/AuthLayout';
import LoginPage from './components/LoginPage';
import RegisterPage from './components/RegisterPage';
import MainDashboard from './components/MainDashboard'; 

function App() {
  return (
    <Routes>
      {/* 1. 기본 경로('/')로 접속하면 '/login'으로 자동 이동시킵니다. */}
      <Route path="/" element={<Navigate to="/login" />} />

      {/* 2. /login, /register 경로는 AuthLayout(중앙 정렬) 안에 렌더링합니다. */}
      <Route element={<AuthLayout />}>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
      </Route>
      
      {/* 3. /dashboard 경로는 MainDashboard를 렌더링합니다. */}
      <Route path="/dashboard" element={<MainDashboard />} /> 
      
      {/* 4. 위에 정의되지 않은 모든 경로는 /login으로 자동 이동시킵니다. */}
      <Route path="*" element={<Navigate to="/login" />} />
    </Routes>
  );
}

export default App;