import React, { useState, useEffect } from 'react';
import styled from 'styled-components';
import apiClient, { getAccessToken } from '../api/client';
import { useNavigate, useSearchParams, Link } from 'react-router-dom';

const Container = styled.div`
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 100%;
  max-width: 420px;
  padding: 20px;
  text-align: center;
`;

const Title = styled.h2`
  font-size: 24px;
  font-weight: 700;
  color: #000;
  margin-bottom: 25px;
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

const LoadingText = styled.p`
  font-size: 16px;
  color: #333;
  padding: 20px;
`;

function GoogleOAuthCallback() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [loadingMessage, setLoadingMessage] = useState('Google Drive와 정보를 교환하고 있습니다. 잠시만 기다려주세요...');

  useEffect(() => {
    const code = searchParams.get('code');
    const state = searchParams.get('state');

    if (!code || !state) {
      setError('유효하지 않은 접근입니다. (code 또는 state 누락)');
      setLoading(false);
      return;
    }

    const verifyCallback = async () => {
      try {
        const token = getAccessToken();
        if (!token) {
          setError('인증 정보가 만료되었습니다. 다시 로그인해주세요.');
          setLoading(false);
          navigate('/login');
          return;
        }

        await apiClient.get('/api/google-drive/oauth/callback', {
          params: { code, state },
        });

        setLoading(false);

        navigate('/dashboard', {
          state: {
            googleConnected: true,
            triggerSyncSources: ['google-drive'],
            syncOverlayMessage: 'Google Drive 데이터 소스를 갱신 중입니다...'
          },
        });
      } catch (err) {
        console.error('Google OAuth Callback Error:', err);
        if (err.response) {
          setError(err.response.data.detail || 'Google Drive 연동에 실패했습니다.');
        } else {
          setError('네트워크 오류가 발생했습니다.');
        }
        setLoading(false);
      }
    };

    verifyCallback();
  }, [searchParams, navigate]);

  return (
    <Container>
      <Title>Google Drive 연동 처리 중...</Title>
      {loading && <LoadingText>{loadingMessage}</LoadingText>}
      {error && (
        <>
          <ErrorMessage>{error}</ErrorMessage>
          <BackLink to="/dashboard">대시보드로 돌아가기</BackLink>
        </>
      )}
    </Container>
  );
}

export default GoogleOAuthCallback;
