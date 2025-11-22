import React, { useState } from 'react';
import styled, { css } from 'styled-components';
import apiClient, { storeTokens } from '../api/client';
// 1. useNavigate, Link import
import { useNavigate, Link } from 'react-router-dom';

// --- Styled Components ---

const Container = styled.div`
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 100%;
  max-width: 380px;
  padding: 20px;
`;

const Header = styled.header`
  text-align: center;
  margin-bottom: 30px;
`;

const LogoText = styled.h1`
  font-size: 28px;
  color: #6200EE;
  margin: 0;
  font-weight: 800;
`;

const Subtitle = styled.p`
  font-size: 14px;
  color: #555;
  margin: 5px 0 0 0;
`;

const Title = styled.h2`
  font-size: 24px;
  font-weight: 700;
  color: #000;
  margin-bottom: 25px;
  align-self: flex-start;
`;

const Form = styled.form`
  display: flex;
  flex-direction: column;
  width: 100%;
`;

const Label = styled.label`
  font-size: 14px;
  font-weight: 600;
  color: #333;
  margin-bottom: 8px;
`;

const Input = styled.input`
  width: 100%;
  padding: 14px 16px;
  font-size: 16px;
  border: 1px solid #E0E0E0;
  background-color: #F7F7F9;
  border-radius: 8px;
  margin-bottom: 16px;

  &::placeholder {
    color: #AAA;
  }

  &:focus {
    outline: none;
    border-color: #6200EE;
    box-shadow: 0 0 0 2px rgba(98, 0, 238, 0.2);
  }

  &:disabled {
    background-color: #E0E0E0;
    cursor: not-allowed;
  }
`;

const Button = styled.button`
  width: 100%;
  padding: 14px;
  font-size: 16px;
  font-weight: 700;
  border-radius: 8px;
  border: none;
  cursor: pointer;
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
  transition: background-color 0.2s;

  ${(props) =>
    props.$primary &&
    css`
      background-color: #6200EE;
      color: white;
      
      &:hover {
        background-color: #5100C4;
      }
    `}

  ${(props) =>
    props.$social === 'kakao' &&
    css`
      background-color: #FEE500;
      color: #3C1E1E;
      
      &:hover {
        background-color: #F0D900;
      }
    `}

  ${(props) =>
    props.$social === 'google' &&
    css`
      background-color: #FFFFFF;
      color: #444;
      border: 1px solid #DADCE0;
      
      &:hover {
        background-color: #F8F9FA;
      }
    `}
  
  &:disabled {
    background-color: #BDBDBD;
    color: #757575;
    cursor: not-allowed;
    
    &:hover {
      background-color: #BDBDBD;
    }
  }
`;

const ErrorMessage = styled.p`
  font-size: 14px;
  color: #D32F2F;
  background-color: #FFEBEE;
  border: 1px solid #FFCDD2;
  border-radius: 8px;
  padding: 12px;
  width: 100%;
  text-align: center;
  margin: -10px 0 16px 0;
`;

const SignUpLink = styled(Link)`
  font-size: 14px;
  color: #555;
  text-decoration: none;
  margin-top: 8px;
  
  &:hover {
    text-decoration: underline;
  }
`;

const Separator = styled.div`
  display: flex;
  align-items: center;
  text-align: center;
  color: #AAA;
  width: 100%;
  margin: 24px 0;
  font-size: 13px;

  &::before,
  &::after {
    content: '';
    flex: 1;
    border-bottom: 1px solid #E0E0E0;
  }

  &::before {
    margin-right: 12px;
  }

  &::after {
    margin-left: 12px;
  }
`;

const DisabledNotice = styled.p`
  width: 100%;
  font-size: 13px;
  color: #777;
  margin: 0 0 12px 0;
  text-align: center;
`;

// --- React Component ---

function LoginPage() {
  const [id, setId] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  
  // 2. useNavigate 훅 사용
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    // vite.config.js의 프록시 설정에 따라 /api로 시작
    const apiUrl = '/api/users/login'; 

    try {
      const response = await apiClient.post(apiUrl, { id, password });
      
      // 3. 닉네임 받아오기
      const { access_token, refresh_token, nickname } = response.data;
      console.log('Login Success:', response.data);

      // 4. 토큰을 세션 스토리지에 저장
      storeTokens({ access_token, refresh_token });
      // 5. 닉네임 저장
      if (nickname) {
        localStorage.setItem('userNickname', nickname);
      }

      // 6. 대시보드로 이동
      navigate('/dashboard');

    } catch (err) {
      if (err.response && err.response.status === 401) {
        setError(err.response.data.detail || '아이디 또는 비밀번호가 올바르지 않습니다.');
      } else {
        console.error('Login Error:', err);
        setError('로그인 중 오류가 발생했습니다. 네트워크를 확인해주세요.');
      }
      setLoading(false);
    } 
  };

  return (
    <Container>
      <Header>
        <LogoText>Arcana</LogoText>
        <Subtitle>정보 파편화의 해결자 플랫폼</Subtitle>
      </Header>

      <Title>로그인</Title>

      {error && <ErrorMessage>{error}</ErrorMessage>}

      <Form onSubmit={handleSubmit}>
        <Label htmlFor="id-input">아이디</Label>
        <Input
          id="id-input"
          type="text"
          value={id}
          onChange={(e) => setId(e.target.value)}
          placeholder="아이디를 입력하세요"
          disabled={loading}
        />

        <Label htmlFor="password-input">비밀번호</Label>
        <Input
          id="password-input"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="비밀번호를 입력하세요"
          disabled={loading}
        />

        <Button type="submit" $primary disabled={loading}>
          {loading ? '로그인 중...' : '로그인'}
        </Button>
      </Form>

      {/* 7. SignUpLink를 Link 컴포넌트로 사용 */}
      <SignUpLink to="/register">
        아직 계정이 없으신가요? 회원가입하러 가기
      </SignUpLink>

      <Separator>또는</Separator>

      <DisabledNotice>카카오톡/구글 소셜 로그인은 현재 준비 중입니다. 아이디 로그인 기능을 이용해주세요.</DisabledNotice>

      <Button
        type="button"
        $social="kakao"
        disabled
        aria-disabled="true"
        title="카카오톡 로그인은 현재 준비 중입니다."
      >
        {/* 아이콘 영역 (추후 svg/img 태그) */}
        카카오톡 로그인 (준비 중)
      </Button>

      <Button
        type="button"
        $social="google"
        disabled
        aria-disabled="true"
        title="구글ID 로그인은 현재 비활성화되어 있습니다."
      >
        {/* 아이콘 영역 (추후 svg/img 태그) */}
        구글ID 로그인 (준비 중)
      </Button>
    </Container>
  );
}

export default LoginPage;