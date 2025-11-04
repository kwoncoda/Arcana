import React, { useState, useEffect } from 'react';
import styled from 'styled-components';
import axios from 'axios';
import { useNavigate, Link } from 'react-router-dom';
// 1. 이미지를 import 합니다. (경로는 src/assets/notion.png 기준)
import notionLogo from '../assets/notion.png';

// --- Styled Components (로그인/회원가입과 동일) ---

const Container = styled.div`
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 100%;
  max-width: 420px;
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

const ContentBox = styled.div`
  width: 100%;
  padding: 24px;
  background-color: #F7F7F9;
  border: 1px solid #E0E0E0;
  border-radius: 8px;
`;

const Description = styled.p`
  font-size: 15px;
  line-height: 1.6;
  color: #333;
  margin-top: 0;
`;

const Button = styled.button`
  width: 100%;
  padding: 14px;
  font-size: 16px;
  font-weight: 700;
  border-radius: 8px;
  border: none;
  cursor: pointer;
  background-color: #000000; // Notion 
  color: white;
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 10px;
  margin-top: 20px;
  
  &:hover {
    background-color: #333;
  }

  &:disabled {
    background-color: #BDBDBD;
    cursor: not-allowed;
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
  margin-top: 16px;
`;

const BackLink = styled(Link)`
  font-size: 14px;
  color: #555;
  text-decoration: none;
  margin-top: 24px;
  
  &:hover {
    text-decoration: underline;
  }
`;

// 2. 버튼 안의 이미지 스타일을 위한 컴포넌트 (선택사항)
const ButtonLogo = styled.img`
  height: 20px;
  width: 20px;
`;


// --- React Component ---

function NotionConnectPage() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const navigate = useNavigate();

  const handleSubmit = async () => {
    setLoading(true);
    setError(null);

    const token = localStorage.getItem('accessToken');

    if (!token) {
      setError('로그인이 필요합니다. 다시 로그인해주세요.');
      setLoading(false);
      setTimeout(() => navigate('/login'), 2000);
      return;
    }
    
    const apiUrl = '/api/notion/connect'; 

    try {
      const res = await axios.post(
        apiUrl, 
        {}, 
        {
          headers: {
            'Authorization': `Bearer ${token}`,
            'Accept': 'application/json'
          }
        }
      );

      const { authorize_url } = res.data;

      if (authorize_url) {
        window.location.href = authorize_url;
      } else {
        setError('연동 URL을 받지 못했습니다.');
      }

    } catch (err) {
      console.error('Notion Connect Error:', err);
      if (err.response) {
        if (err.response.status === 401) {
          setError('인증에 실패했습니다. 다시 로그인해주세요.');
          localStorage.removeItem('accessToken');
          localStorage.removeItem('refreshToken');
          setTimeout(() => navigate('/login'), 2000);
        } else if (err.response.status === 404) {
          setError('워크스페이스를 찾을 수 없습니다. (404)');
        } else {
          setError(err.response.data.detail || '연동 중 오류가 발생했습니다.');
        }
      } else {
        setError('네트워크 오류가 발생했습니다. 잠시 후 다시 시도해주세요.');
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

      <Title>데이터 소스 연동</Title>

      <ContentBox>
        <Description>
          Arcana가 Notion 워크스페이스에 접근할 수 있도록 권한을 부여합니다.
          <br/><br/>
          '연동 시작하기' 버튼을 누르면 Notion 권한 동의 페이지로 이동합니다.
        </Description>
        
        <Button onClick={handleSubmit} disabled={loading}>
          {/* 3. import한 변수를 src에 사용하고, 스타일(혹은 크기)을 적용합니다. */}
          <ButtonLogo src={notionLogo} alt="Notion 로고" />
          Notion 연동 시작하기
        </Button>
        
        {error && <ErrorMessage>{error}</ErrorMessage>}
      </ContentBox>

      <BackLink to="/dashboard">← 대시보드로 돌아가기</BackLink>
    </Container>
  );
}

export default NotionConnectPage;

