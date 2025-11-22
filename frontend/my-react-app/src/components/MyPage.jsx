import React, { useState, useEffect } from 'react';
import styled, { css } from 'styled-components';
import { useNavigate, Link } from 'react-router-dom';
import apiClient, { clearTokens } from '../api/client';

// --- Styled Components (로그인 페이지와 유사) ---

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
  font-size: 16px;
  line-height: 1.6;
  color: #333;
  margin-top: 0;
  margin-bottom: 24px;
  
  strong {
    color: #6200EE;
  }
`;

const Button = styled.button`
  width: 100%;
  padding: 14px;
  font-size: 16px;
  font-weight: 700;
  border-radius: 8px;
  border: 1px solid transparent;
  cursor: pointer;
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 10px;
  margin-top: 12px;
  transition: all 0.2s ease;

  /* 기본 (로그아웃 버튼) */
  ${(props) =>
    props.$primary &&
    css`
      background-color: #6200EE;
      color: white;
      border-color: #6200EE;
      
      &:hover {
        background-color: #5100C4;
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(98, 0, 238, 0.2);
      }
    `}

  /* 회원탈퇴 (경고 버튼) */
  ${(props) =>
    props.$destructive &&
    css`
      background-color: transparent;
      color: #D32F2F;
      border-color: #D32F2F;
      
      &:hover {
        background-color: #FFEBEE;
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(211, 47, 47, 0.15);
      }
    `}
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

const StatusMessage = styled.p`
  font-size: 14px;
  color: #1B5E20;
  background-color: #E8F5E9;
  border: 1px solid #A5D6A7;
  border-radius: 8px;
  padding: 12px;
  width: 100%;
  text-align: center;
  margin-top: 16px;
`;

const ModalOverlay = styled.div`
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.55);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 999;
`;

const ModalCard = styled.div`
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.15);
  width: 90%;
  max-width: 420px;
  padding: 24px;
  text-align: center;
`;

const ModalTitle = styled.h3`
  margin: 0 0 12px;
  font-size: 20px;
  font-weight: 800;
`;

const ModalMessage = styled.p`
  margin: 0 0 24px;
  font-size: 15px;
  color: #444;
  line-height: 1.6;
`;

const ModalActions = styled.div`
  display: flex;
  gap: 12px;
  justify-content: center;
`;

const ModalButton = styled.button`
  flex: 1;
  padding: 12px 0;
  border-radius: 10px;
  border: 1px solid transparent;
  font-weight: 700;
  cursor: pointer;
  transition: all 0.2s ease;

  ${(props) =>
    props.$variant === 'cancel'
      ? css`
          background: #f5f5f5;
          color: #333;
          border-color: #e0e0e0;

          &:hover {
            background: #ebebeb;
          }
        `
      : css`
          background: #d32f2f;
          color: #fff;
          border-color: #d32f2f;

          &:hover {
            background: #b71c1c;
            transform: translateY(-1px);
            box-shadow: 0 4px 12px rgba(211, 47, 47, 0.25);
          }
          &:disabled {
            opacity: 0.7;
            cursor: not-allowed;
            transform: none;
            box-shadow: none;
          }
        `};
`;

// --- React Component ---

function MyPage() {
  const [nickname, setNickname] = useState('사용자');
  const [error, setError] = useState(null);
  const [status, setStatus] = useState(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [isConfirmOpen, setIsConfirmOpen] = useState(false);
  const [isSuccessModalOpen, setIsSuccessModalOpen] = useState(false);
  const navigate = useNavigate();

  // 페이지 로드 시 닉네임 불러오기
  useEffect(() => {
    const storedNickname = localStorage.getItem('userNickname');
    if (storedNickname) {
      setNickname(storedNickname);
    }
  }, []);

  // 로그아웃 핸들러
  const clearProfileState = () => {
    clearTokens();
    window.sessionStorage?.removeItem('userNickname');
    window.localStorage?.removeItem('userNickname');
  };

  // 로그아웃 핸들러
  const handleLogout = () => {
    clearProfileState();
    navigate('/login');
  };

  // 회원탈퇴 핸들러
  const handleDeleteAccount = () => {
    setError(null);
    setStatus(null);
    if (isDeleting) return;
    setIsConfirmOpen(true);
  };

  const confirmDeleteAccount = async () => {
    try {
      setIsDeleting(true);
      await apiClient.delete('/api/users/me');
      clearProfileState();
      setStatus('탈퇴되었습니다. 로그인 화면으로 이동합니다.');
      setIsSuccessModalOpen(true);
      setTimeout(() => navigate('/login', { replace: true }), 1200);
    } catch (err) {
      const detail = err?.response?.data?.detail;
      setError(detail || '회원 탈퇴 처리 중 오류가 발생했습니다. 다시 시도해주세요.');
    } finally {
      setIsDeleting(false);
      setIsConfirmOpen(false);
    }
  };

  return (
    <Container>
      <Header>
        <LogoText>Arcana</LogoText>
        <Subtitle>정보 파편화의 해결자 플랫폼</Subtitle>
      </Header>

      <Title>마이페이지</Title>

      <ContentBox>
        <Description>
          안녕하세요, <strong>{nickname}</strong>님.
          <br />
          계정 관리를 하실 수 있습니다.
        </Description>
        
        <Button $primary onClick={handleLogout}>
          로그아웃
        </Button>

        <Button $destructive onClick={handleDeleteAccount} disabled={isDeleting}>
          회원 탈퇴
        </Button>

        {status && <StatusMessage>{status}</StatusMessage>}
        {error && <ErrorMessage>{error}</ErrorMessage>}
      </ContentBox>

      <BackLink to="/dashboard">← 대시보드로 돌아가기</BackLink>

      {isConfirmOpen && (
        <ModalOverlay>
          <ModalCard>
            <ModalTitle>회원 탈퇴</ModalTitle>
            <ModalMessage>
              정말로 회원을 탈퇴하시겠습니까? 연결된 데이터도 비활성화됩니다.
            </ModalMessage>
            <ModalActions>
              <ModalButton $variant="cancel" onClick={() => setIsConfirmOpen(false)} disabled={isDeleting}>
                취소
              </ModalButton>
              <ModalButton onClick={confirmDeleteAccount} disabled={isDeleting}>
                {isDeleting ? '처리 중...' : '탈퇴하기'}
              </ModalButton>
            </ModalActions>
          </ModalCard>
        </ModalOverlay>
      )}

      {isSuccessModalOpen && (
        <ModalOverlay>
          <ModalCard>
            <ModalTitle>탈퇴되었습니다</ModalTitle>
            <ModalMessage>잠시 후 로그인 화면으로 이동합니다.</ModalMessage>
          </ModalCard>
        </ModalOverlay>
      )}
    </Container>
  );
}

export default MyPage;