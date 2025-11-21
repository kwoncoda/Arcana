import React, { useEffect, useState } from 'react';
import styled from 'styled-components';
import axios from 'axios';
import { useNavigate, Link, useLocation } from 'react-router-dom';
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

const IntegrationGrid = styled.div`
  display: grid;
  width: 100%;
  gap: 20px;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
`;

const ContentBox = styled.div`
  width: 100%;
  padding: 24px;
  background-color: #F7F7F9;
  border: 1px solid #E0E0E0;
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  gap: 16px;
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
  background-color: #000000; // 기본값은 Notion 컬러
  color: white;
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 10px;

  &:hover {
    filter: brightness(0.9);
  }

  &:disabled {
    background-color: #BDBDBD;
    cursor: not-allowed;
  }
`;

const GoogleButton = styled(Button)`
  background-color: #1A73E8;
`;

const ProviderBadge = styled.div`
  width: 32px;
  height: 32px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: ${(props) => props.bg || '#E0E0E0'};
  color: ${(props) => props.color || '#000'};
  font-weight: 700;
  font-size: 16px;
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

const SuccessMessage = styled.p`
  font-size: 14px;
  color: #1B5E20;
  background-color: #E8F5E9;
  border: 1px solid #A5D6A7;
  border-radius: 8px;
  padding: 12px;
  width: 100%;
  text-align: center;
  margin-top: 16px;
  font-weight: 700;
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
  const [googleLoading, setGoogleLoading] = useState(false);
  const [googleError, setGoogleError] = useState(null);
  const [successMessage, setSuccessMessage] = useState('');
  const [syncWarning, setSyncWarning] = useState('');
  const location = useLocation();
  const navigate = useNavigate();

  useEffect(() => {
    if (location.state?.notionConnected) {
      setSuccessMessage('노션이 연동되었습니다.');
      if (location.state.notionSyncFailed) {
        setSyncWarning('연동은 완료되었지만 지식 베이스 갱신 중 오류가 발생했습니다. 다시 시도해주세요.');
      }

      // 상태를 초기화하여 새로 고침 시 메시지가 중복되지 않도록 함
      navigate('.', { replace: true, state: {} });
    }
  }, [location.state, navigate]);

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
        setLoading(false);
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

  const handleGoogleConnect = async () => {
    setGoogleLoading(true);
    setGoogleError(null);

    const token = localStorage.getItem('accessToken');

    if (!token) {
      setGoogleError('로그인이 필요합니다. 다시 로그인해주세요.');
      setGoogleLoading(false);
      setTimeout(() => navigate('/login'), 2000);
      return;
    }

    const apiUrl = '/api/google-drive/connect';

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
        setGoogleError('연동 URL을 받지 못했습니다.');
        setGoogleLoading(false);
      }
    } catch (err) {
      console.error('Google Drive Connect Error:', err);
      if (err.response) {
        if (err.response.status === 401) {
          setGoogleError('인증에 실패했습니다. 다시 로그인해주세요.');
          localStorage.removeItem('accessToken');
          localStorage.removeItem('refreshToken');
          setTimeout(() => navigate('/login'), 2000);
        } else if (err.response.status === 404) {
          setGoogleError('워크스페이스를 찾을 수 없습니다. (404)');
        } else {
          setGoogleError(err.response.data.detail || '연동 중 오류가 발생했습니다.');
        }
      } else {
        setGoogleError('네트워크 오류가 발생했습니다. 잠시 후 다시 시도해주세요.');
      }
      setGoogleLoading(false);
    }
  };

  return (
    <Container>
      <Header>
        <LogoText>Arcana</LogoText>
        <Subtitle>정보 파편화의 해결자 플랫폼</Subtitle>
      </Header>

      <Title>데이터 소스 연동</Title>

      <IntegrationGrid>
        <ContentBox>
          <Description>
            Arcana가 Notion 워크스페이스에 접근할 수 있도록 권한을 부여합니다.
            <br/><br/>
            '연동 시작하기' 버튼을 누르면 Notion 권한 동의 페이지로 이동합니다.
          </Description>

          <Button onClick={handleSubmit} disabled={loading}>
            <ButtonLogo src={notionLogo} alt="Notion 로고" />
            Notion 연동 시작하기
          </Button>

          {successMessage && <SuccessMessage>{successMessage}</SuccessMessage>}
          {syncWarning && <ErrorMessage>{syncWarning}</ErrorMessage>}
          {error && <ErrorMessage>{error}</ErrorMessage>}
        </ContentBox>

        <ContentBox>
          <Description>
            Arcana가 Google Drive 파일에 접근할 수 있도록 권한을 부여합니다.
            <br/><br/>
            '연동 시작하기' 버튼을 누르면 Google 계정 선택 및 권한 동의 페이지로 이동합니다.
          </Description>

          <GoogleButton onClick={handleGoogleConnect} disabled={googleLoading}>
            <ProviderBadge bg="#E8F0FE" color="#1A73E8">G</ProviderBadge>
            Google Drive 연동 시작하기
          </GoogleButton>

          {googleError && <ErrorMessage>{googleError}</ErrorMessage>}
        </ContentBox>
      </IntegrationGrid>

      <BackLink to="/dashboard">← 대시보드로 돌아가기</BackLink>
    </Container>
  );
}

export default NotionConnectPage;

