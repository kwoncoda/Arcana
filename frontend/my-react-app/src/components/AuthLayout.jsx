import React from 'react';
import { Outlet } from 'react-router-dom';
import styled from 'styled-components';

// 로그인/회원가입 페이지만 중앙 정렬하는 레이아웃
const AuthContainer = styled.div`
  display: flex;
  justify-content: center;
  align-items: center;
  width: 100%;
  min-height: 100vh;
  padding: 20px;
  background-color: #FFFFFF; /* 흰 배경 */
`;

function AuthLayout() {
  // Outlet은 App.jsx의 자식 라우트(LoginPage, RegisterPage)를
  // 이 위치에 렌더링하라는 의미입니다.
  return (
    <AuthContainer>
      <Outlet />
    </AuthContainer>
  );
}

export default AuthLayout;

