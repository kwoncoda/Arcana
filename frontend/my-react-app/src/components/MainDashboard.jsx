import React, { useState, useEffect, useCallback, useRef } from 'react';
import styled, { keyframes } from 'styled-components';
import { useNavigate, Link } from 'react-router-dom';
import axios from 'axios';
import { 
  Home, 
  MessageSquare, 
  Database, 
  Settings, 
  Plus,
  RefreshCw,
  ChevronDown, 
  User, 
  Send, 
  Paperclip,
  Activity,
  FileText,
  AlertCircle,
  CheckCircle,
  HelpCircle,
  Brain,
  Copy
} from 'lucide-react';

// --- Layout Containers ---

const DashboardContainer = styled.div`
  display: flex;
  width: 100%;
  height: 100vh;
  background-color: #F9FAFB;
`;

const Sidebar = styled.nav`
  width: 260px;
  background-color: #1F2328; 
  color: #A0AEC0; 
  padding: 24px 16px;
  display: flex;
  flex-direction: column;
  flex-shrink: 0;

  /* --- 768px 이하면 사이드바 숨김 --- */
  @media (max-width: 768px) {
    display: none;
  }
`;

const MainContent = styled.main`
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden; 
`;

const TopBar = styled.header`
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 24px;
  background-color: #FFFFFF;
  border-bottom: 1px solid #E2E8F0;
  height: 70px;
  flex-shrink: 0;
`;

const TopBarActions = styled.div`
  display: flex;
  align-items: center;
  gap: 12px;
`;

const RefreshButton = styled.button`
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 14px;
  background-color: #EDF2F7;
  color: #1A202C;
  border: 1px solid #CBD5E0;
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
  font-weight: 500;
  transition: background-color 0.2s ease;

  &:hover {
    background-color: #E2E8F0;
  }

  &:disabled {
    cursor: not-allowed;
    opacity: 0.65;
    background-color: #E2E8F0;
  }
`;

const SYNC_STATUS_COLORS = {
  success: { bg: '#EDFDF7', border: '#9AE6B4', color: '#22543D' },
  error: { bg: '#FFF5F5', border: '#FEB2B2', color: '#742A2A' },
  warning: { bg: '#FFFBEB', border: '#FBD38D', color: '#744210' },
  info: { bg: '#EBF8FF', border: '#90CDF4', color: '#2B6CB0' },
};

const SyncStatusBar = styled.div`
  margin: 12px 24px 0;
  border-radius: 8px;
  padding: 12px 16px;
  font-size: 13px;
  font-weight: 500;
  background-color: ${({ $variant }) => (SYNC_STATUS_COLORS[$variant] || SYNC_STATUS_COLORS.info).bg};
  border: 1px solid ${({ $variant }) => (SYNC_STATUS_COLORS[$variant] || SYNC_STATUS_COLORS.info).border};
  color: ${({ $variant }) => (SYNC_STATUS_COLORS[$variant] || SYNC_STATUS_COLORS.info).color};
`;

const ChatWrapper = styled.div`
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background-color: #FFFFFF;
  min-width: 300px; 
`;

const AnalyticsSidebar = styled.aside`
  width: 320px;
  flex-shrink: 0;
  background-color: #F9FAFB;
  padding: 24px;
  overflow-y: auto;
  border-left: 1px solid #E2E8F0;

  /* --- 1280px 이하면 분석 사이드바 숨김 --- */
  @media (max-width: 1280px) {
    display: none;
  }
`;


// --- Sidebar Components ---

const LogoHeader = styled.div`
  padding: 0 8px;
  margin-bottom: 24px;
`;

const LogoText = styled.h1`
  font-size: 24px;
  color: #FFFFFF;
  margin: 0 0 4px 0;
  font-weight: 700;
  display: flex;
  align-items: center;
  gap: 8px;
`;

const Subtitle = styled.p`
  font-size: 12px;
  color: #A0AEC0;
  margin: 0;
`;

const NavMenu = styled.ul`
  list-style: none;
  padding: 0;
  margin: 0;
  flex-grow: 1;
`;

const NavItem = styled.li`
  display: flex;
  align-items: center;
  padding: 10px 12px;
  border-radius: 6px;
  margin-bottom: 4px;
  font-size: 14px;
  font-weight: 500;
  color: #CBD5E0;
  cursor: pointer;
  gap: 10px;
  text-decoration: none; 

  &:hover {
    background-color: #2D3748;
  }
`;

const SectionTitle = styled.h3`
  font-size: 12px;
  font-weight: 600;
  color: #718096;
  text-transform: uppercase;
  padding: 8px 12px;
  margin: 16px 0 8px 0;
`;

const DataSourceItem = styled(NavItem)`
  color: #A0AEC0;
  
  span {
    width: 20px;
    height: 20px;
    border-radius: 4px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 12px;
    font-weight: 700;
  }
`;

const EmptyDataSource = styled.div`
  padding: 10px 12px;
  font-size: 14px;
  color: #718096;
  font-style: italic;
`;


const UpgradeBanner = styled.div`
  background-color: #2D3748;
  border: 1px solid #4A5568;
  border-radius: 8px;
  padding: 16px;
  margin-top: auto;
`;

const UpgradeText = styled.p`
  font-size: 13px;
  color: #CBD5E0;
  line-height: 1.5;
  margin: 0;
`;


// --- TopBar Components ---

const TopBarHeader = styled.div`
  h2 {
    font-size: 18px;
    color: #1A202C;
    margin: 0;
  }
  p {
    font-size: 13px;
    color: #718096;
    margin: 4px 0 0 0;

    /* 500px 이하 숨김 */
    @media (max-width: 500px) {
      display: none;
    }
  }
`;

const TopBarStats = styled.div`
  display: flex;
  align-items: center;
  gap: 24px;

  /* --- 1024px 이하 숨김 --- */
  @media (max-width: 1024px) {
    display: none;
  }
`;

const StatItem = styled.div`
  display: flex;
  align-items: center;
  gap: 12px;
  
  .icon {
    width: 40px;
    height: 40px;
    border-radius: 50%;
    background-color: #EBF4FF;
    color: #4299E1;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .text {
    span {
      display: block;
      font-size: 16px;
      font-weight: 600;
      color: #2D3748;
    }
    p {
      font-size: 12px;
      color: #718096;
      margin: 2px 0 0 0;
    }
  }
`;

const UserProfile = styled.div`
  display: flex;
  align-items: center;
  gap: 10px;
  cursor: pointer;
  
  .avatar {
    width: 36px;
    height: 36px;
    border-radius: 50%;
    background-color: #4A5568;
    color: white;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 14px;
    font-weight: 600;
  }
  
  .user-info {
    display: flex;
    align-items: center;
    gap: 4px;

    span {
      font-size: 14px;
      font-weight: 500;
      color: #2D3748;
    }

    @media (max-width: 500px) {
      display: none;
    }
  }
`;

// --- ChatWrapper Components ---

const ChatContainer = styled.div`
  flex-grow: 1;
  padding: 24px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 20px;
`;

const MessageWrapper = styled.div`
  display: flex;
  flex-direction: column;
  align-items: ${props => (props.$role === 'user' ? 'flex-end' : 'flex-start')};
`;

const MessageHeader = styled.span`
  font-size: 13px;
  font-weight: 600;
  color: #4A5568;
  margin-bottom: 6px;
`;

const MessageBubble = styled.div`
  max-width: 80%;
  padding: 12px 16px;
  border-radius: 12px;
  font-size: 14px;
  line-height: 1.6;
  white-space: pre-wrap;
`;

const UserMessageBubble = styled(MessageBubble)`
  background-color: #6200EE;
  color: white;
  border-top-right-radius: 0;
`;

const AIMessageBubble = styled(MessageBubble)`
  background-color: #F7F7F9;
  color: #1A202C;
  border: 1px solid #E2E8F0;
  border-top-left-radius: 0;
  position: relative;
`;

const MessageToolbar = styled.div`
  display: flex;
  justify-content: flex-end;
  margin-top: 10px;
  padding-top: 8px;
  border-top: 1px solid #E2E8F0;
`;

const CopyButton = styled.button`
  background: none;
  border: none;
  color: #718096;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  padding: 4px;

  &:hover {
    color: #1A202C;
  }
`;

const SourceLink = styled.a`
  font-size: 12px;
  color: #4299E1;
  text-decoration: none;
  display: block;
  margin-top: 8px;
  &:hover { text-decoration: underline; }
`;

const pulse = keyframes`
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
`;

const LoadingDots = styled.div`
  display: flex;
  gap: 4px;
  padding: 12px 16px;

  & > div {
    width: 8px;
    height: 8px;
    background-color: #A0AEC0;
    border-radius: 50%;
    animation: ${pulse} 1.2s cubic-bezier(0, 0.5, 0.5, 1) infinite;
  }

  & > div:nth-child(1) { animation-delay: -0.24s; }
  & > div:nth-child(2) { animation-delay: -0.12s; }
  & > div:nth-child(3) { animation-delay: 0s; }
`;


const WelcomeMessage = styled.div`
  background-color: #F7F7F9;
  border: 1px solid #E2E8F0;
  border-radius: 8px;
  padding: 20px;
  
  h3 {
    font-size: 16px;
    color: #2D3748;
    margin: 0 0 12px 0;
  }

  p {
    font-size: 14px;
    color: #4A5568;
    line-height: 1.6;
    margin: 0 0 16px 0;
  }

  ul {
    list-style: none;
    padding-left: 0;
    margin: 0;
    display: flex;
    flex-direction: column;
    gap: 8px;

    li {
      font-size: 14px;
      color: #4299E1;
      cursor: pointer;
      &:hover { text-decoration: underline; }
    }
  }
`;

const ChatInputArea = styled.div`
  border-top: 1px solid #E2E8F0;
  padding: 16px 24px;
  background-color: #FFFFFF;
`;

const ChatTextarea = styled.textarea`
  width: 100%;
  border: none;
  outline: none;
  resize: none;
  font-size: 14px;
  color: #2D3748;
  line-height: 1.6;
  min-height: 24px;
  max-height: 200px;
  font-family: inherit;
  overflow-y: auto;

  &::placeholder {
    color: #A0AEC0;
  }
`;

const ChatToolbar = styled.div`
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 8px;
`;

const ToolbarLeft = styled.div`
  display: flex;
  align-items: center;
  gap: 12px;
  color: #718096;
`;

const ToolbarRight = styled.div`
  display: flex;
  align-items: center;
  gap: 8px;
`;

const SendButton = styled.button`
  background-color: #6200EE;
  color: white;
  border: none;
  border-radius: 6px;
  padding: 8px 12px;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  font-weight: 500;

  &:hover {
    background-color: #5100C4;
  }

  &:disabled {
    background-color: #BDBDBD;
    cursor: not-allowed;
  }
`;

// --- AnalyticsSidebar Components ---

const AnalyticsCard = styled.div`
  background-color: #FFFFFF;
  border: 1px solid #E2E8F0;
  border-radius: 8px;
  margin-bottom: 20px;
  padding: 20px;
  
  h3 {
    font-size: 12px;
    font-weight: 600;
    color: #718096;
    text-transform: uppercase;
    margin: 0 0 16px 0;
    border-bottom: 1px solid #E2E8F0;
    padding-bottom: 12px;
  }
`;

const KnowledgeStat = styled.div`
  display: flex;
  align-items: center;
  gap: 16px;
  
  .icon {
    width: 48px;
    height: 48px;
    border-radius: 8px;
    background-color: #E6FFFA;
    color: #38B2AC;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .text {
    span {
      display: block;
      font-size: 24px;
      font-weight: 700;
      color: #2D3748;
    }
    p {
      font-size: 13px;
      color: #718096;
      margin: 2px 0 0 0;
    }
  }
`;

// --- (사이드바 렌더링용) 아이콘/스타일 맵 ---
const providerDetails = {
  notion: { name: 'Notion', icon: 'N', color: '#000000', bg: '#E0E0E0' },
  slack: { name: 'Slack', icon: 'S', color: '#4A154B', bg: '#EFE1EF' },
  jira: { name: 'Jira', icon: 'J', color: '#0052CC', bg: '#DEEBFF' },
  "google-drive": { name: 'Google Drive', icon: 'G', color: '#1A73E8', bg: '#E8F0FE' },
};

const getProviderDetails = connection => {
  const providerKey = (connection?.type || connection?.name || '').toLowerCase();
  const baseDetails = providerDetails[providerKey];

  if (baseDetails) {
    return baseDetails;
  }

  const fallbackName = connection?.name || connection?.type || 'Unknown';
  const fallbackIcon = fallbackName ? fallbackName.charAt(0).toUpperCase() : '?';

  return {
    name: fallbackName,
    icon: fallbackIcon,
    color: '#333',
    bg: '#eee',
  };
};

// 닉네임 이니셜 생성 헬퍼 함수
const getInitials = (name) => {
  if (!name) return 'U';
  const parts = name.trim().split(' ');
  // "Gildong Hong" -> "GH"
  if (parts.length > 1 && parts[parts.length - 1]) {
    return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
  }
  // "Gildong" -> "G"
  return name[0].toUpperCase();
};


// --- React Component ---

function MainDashboard() {
  const [chatInput, setChatInput] = useState('');
  const [connections, setConnections] = useState([]);
  const [loadingConnections, setLoadingConnections] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [syncMessage, setSyncMessage] = useState(null);
  const navigate = useNavigate();

  // 1. 닉네임/이니셜 state 추가
  const [userNickname, setUserNickname] = useState('User');
  const [userInitials, setUserInitials] = useState('U');

  const [chatMessages, setChatMessages] = useState([]); 
  const [isChatLoading, setIsChatLoading] = useState(false); 
  const chatContainerRef = useRef(null); 
  const textareaRef = useRef(null); 
  
  // 2. 한글 입력 버그 수정을 위한 state
  const [isComposing, setIsComposing] = useState(false);

  const fetchConnections = useCallback(async (tokenOverride) => {
    setLoadingConnections(true);
    try {
      const token = tokenOverride || localStorage.getItem('accessToken');
      if (!token) {
        navigate('/login');
        return [];
      }

      const res = await axios.get('/api/users/connections', {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });

      const fetchedConnections = res.data.connections || [];
      setConnections(fetchedConnections);
      return fetchedConnections;
    } catch (err) {
      console.error('Failed to fetch connections:', err);
      const status = err?.response?.status;
      if (status === 401 || status === 404) {
        localStorage.removeItem('accessToken');
        localStorage.removeItem('refreshToken');
        localStorage.removeItem('userNickname'); // 닉네임도 함께 삭제
        navigate('/login');
      }
      throw err;
    } finally {
      setLoadingConnections(false);
    }
  }, [navigate]);

  useEffect(() => {
    // 3. 페이지 로드 시 닉네임 불러오기
    const nickname = localStorage.getItem('userNickname');
    if (nickname) {
      setUserNickname(nickname);
      setUserInitials(getInitials(nickname));
    }
    
    fetchConnections().catch(() => {});
  }, [fetchConnections]);

  // 5. 채팅창 스크롤 맨 아래로 이동
  useEffect(() => {
    if (chatContainerRef.current) {
      chatContainerRef.current.scrollTop = chatContainerRef.current.scrollHeight;
    }
  }, [chatMessages, isChatLoading]);

  // 6. Textarea 높이 자동 조절
  const autoResizeTextarea = (element) => {
    element.style.height = 'auto'; 
    element.style.height = `${element.scrollHeight}px`; 
  };

  const handleTextareaChange = (e) => {
    setChatInput(e.target.value);
    autoResizeTextarea(e.target);
  };

  // 4. handleLogout 함수는 MyPage.jsx로 이동했으므로 여기서는 삭제됨.

  const handleRefreshKnowledge = async () => {
    // ... (기존 갱신 로직)
    if (syncing) return;

    const token = localStorage.getItem('accessToken');
    if (!token) {
      setSyncMessage({
        variant: 'error',
        message: '로그인이 필요합니다. 다시 로그인해주세요.'
      });
      navigate('/login');
      return;
    }

    const headers = {
      'Authorization': `Bearer ${token}`
    };

    setSyncing(true);
    setSyncMessage({
      variant: 'info',
      message: '지식 베이스를 갱신 중입니다...'
    });

    let availableConnections = connections;

    try {
      try {
        const fetchedConnections = await fetchConnections(token);
        if (Array.isArray(fetchedConnections)) {
          availableConnections = fetchedConnections;
        }
      } catch (error) {
        const status = error?.response?.status;
        if (status === 401 || status === 404) {
          setSyncMessage({
            variant: 'error',
            message: '세션이 만료되었습니다. 다시 로그인해주세요.'
          });
          return;
        }
        console.error('Failed to refresh connections before syncing:', error);
      }

      const connectedSources = (availableConnections || []).filter(
        (conn) => conn && (conn.status === 'connected' || conn.connected)
      );

      if (connectedSources.length === 0) {
        setSyncMessage({
          variant: 'warning',
          message: '연결된 데이터 소스가 없습니다. 먼저 데이터 소스를 연동해주세요.'
        });
        return;
      }

      const successMessages = [];
      const skippedSources = [];
      const failureMessages = [];
      let unauthorizedDetected = false;

      for (const source of connectedSources) {
        if (unauthorizedDetected) {
          break;
        }

        const type = (source?.type || '').toLowerCase();
        const displayName = source?.name || source?.type || 'Unknown';

        if (type === 'notion') {
          try {
            const response = await axios.post('/api/notion/pages/pull', {}, { headers });
            const ingested = response?.data?.ingested_chunks;
            if (typeof ingested === 'number') {
              successMessages.push(`${displayName}: ${ingested}개 청크 갱신`);
            } else {
              successMessages.push(`${displayName}: 갱신 완료`);
            }
          } catch (error) {
            const status = error?.response?.status;
            if (status === 401) {
              unauthorizedDetected = true;
              localStorage.removeItem('accessToken');
              localStorage.removeItem('refreshToken');
              localStorage.removeItem('userNickname'); // 닉네임 삭제
              navigate('/login');
              failureMessages.push(`${displayName}: 인증이 만료되었습니다. 다시 로그인해주세요.`);
            } else {
              const detail =
                error?.response?.data?.detail ||
                error?.message ||
                '알 수 없는 오류가 발생했습니다.';
              failureMessages.push(`${displayName}: ${detail}`);
            }
          }
        } else {
          skippedSources.push(displayName);
        }
      }

      if (unauthorizedDetected) {
        setSyncMessage({
          variant: 'error',
          message: failureMessages.join(' ')
        });
        return;
      }

      if (failureMessages.length > 0) {
        setSyncMessage({
          variant: 'error',
          message: `일부 데이터 소스 갱신에 실패했습니다. ${failureMessages.join(' | ')}`
        });
        return;
      }

      if (successMessages.length > 0 && skippedSources.length > 0) {
        setSyncMessage({
          variant: 'info',
          message: `${successMessages.join(' | ')}. ${skippedSources.join(', ')} 데이터 소스는 아직 자동 갱신을 지원하지 않습니다.`
        });
        return;
      }

      if (successMessages.length > 0) {
        setSyncMessage({
          variant: 'success',
          message: `모든 연결된 데이터 소스를 갱신했습니다. ${successMessages.join(' | ')}`
        });
        return;
      }

      if (skippedSources.length > 0) {
        setSyncMessage({
          variant: 'warning',
          message: `${skippedSources.join(', ')} 데이터 소스는 아직 자동 갱신을 지원하지 않습니다.`
        });
        return;
      }

      setSyncMessage({
        variant: 'info',
        message: '지식 베이스 갱신을 완료했습니다.'
      });
    } finally {
      setSyncing(false);
    }
  };

  // 7. 메시지 전송 핸들러
  const handleSendMessage = async () => {
    const query = chatInput.trim();
    // 5. isComposing 확인
    if (!query || isChatLoading || isComposing) return;

    setIsChatLoading(true);
    setChatInput(''); 
    if (textareaRef.current) {
      autoResizeTextarea(textareaRef.current);
    }

    const token = localStorage.getItem('accessToken');
    if (!token) {
      navigate('/login');
      return;
    }

    setChatMessages((prev) => [...prev, { role: 'user', content: query }]);

    try {
      const res = await axios.post(
        '/api/aiagent/search', 
        { query },
        { headers: { 'Authorization': `Bearer ${token}` } }
      );
      
      const { answer, notion_page_url, notion_page_id } = res.data;

      setChatMessages((prev) => [
        ...prev,
        {
          role: 'ai',
          content: answer,
          sourcePage: notion_page_url,
          sourceId: notion_page_id,
        },
      ]);
    } catch (err) {
      console.error('AI Search Error:', err);
      let errorMessage = '답변을 생성하는 중 오류가 발생했습니다.';
      if (err.response) {
        if (err.response.status === 401) {
          navigate('/login');
          return;
        }
        if (err.response.data.detail) {
          errorMessage = `오류: ${err.response.data.detail}`;
        }
      }
      setChatMessages((prev) => [
        ...prev,
        { role: 'ai', content: errorMessage, isError: true },
      ]);
    } finally {
      setIsChatLoading(false);
    }
  };

  // 8. Enter / Shift+Enter 키 처리
  const handleKeyDown = (e) => {
    // 6. isComposing 아닐 때만 전송
    if (e.key === 'Enter' && !e.shiftKey && !isComposing) {
      e.preventDefault(); 
      handleSendMessage();
    }
  };

  // 9. 복사 버튼 핸들러
  const handleCopy = (text) => {
    const textArea = document.createElement('textarea');
    textArea.value = text;
    document.body.appendChild(textArea);
    textArea.select();
    try {
      document.execCommand('copy');
    } catch (err) {
      console.error('Failed to copy text:', err);
    }
    document.body.removeChild(textArea);
  };

  const renderConnectionItem = (conn) => {
    const details = getProviderDetails(conn);
    
    if (conn.status === 'connected' || conn.connected === true) {
      return (
        <DataSourceItem key={conn.type || details.name}>
          <span style={{ color: details.color, backgroundColor: details.bg }}>
            {details.icon}
          </span>
          {details.name}
        </DataSourceItem>
      );
    }
    return null; 
  };

  return (
    <DashboardContainer>
      
      {/* --- 1. Sidebar (Left) --- */}
      <Sidebar>
        <LogoHeader>
          <LogoText><Brain size={24} /> Arcana</LogoText>
          <Subtitle>정보 파편화의 해결자 플랫폼</Subtitle>
        </LogoHeader>

        <NavMenu>
          <SectionTitle>MAIN DASHBOARD</SectionTitle>
          <NavItem><Home size={18} /> 메인화면</NavItem>
          <NavItem><MessageSquare size={18} /> AI 채팅 인터페이스</NavItem>

          <SectionTitle>DATA SOURCES</SectionTitle>
          
          {loadingConnections ? (
            <EmptyDataSource>연결된 소스 로딩 중...</EmptyDataSource>
          ) : connections.length > 0 ? (
            connections.map(renderConnectionItem)
          ) : (
            <EmptyDataSource>
              연결된 소스가 없습니다.
            </EmptyDataSource>
          )}

          <NavItem as={Link} to="/connect/notion">
            <Plus size={18} /> Add more sources
          </NavItem>
        </NavMenu>

        <UpgradeBanner>
          <UpgradeText>
            프로 요금제의 저장 공간이 거의 다 찼습니다. 프리미엄 요금제로 업그레이드하세요.
          </UpgradeText>
        </UpgradeBanner>
      </Sidebar>

      {/* --- 2. Main Content (Center) --- */}
      <MainContent>
        {/* 2.1 TopBar */}
        <TopBar>
          <TopBarHeader>
            <h2>Arcana AI 정보 어시턴트</h2>
            <p>조직의 지식에 기반하여 궁금증을 질문해보세요</p>
          </TopBarHeader>

          <TopBarStats>
            <StatItem>
              <div className="icon"><HelpCircle size={20}/></div>
              <div className="text">
                <span>1,234</span>
                <p>오늘 사용된 쿼리</p>
              </div>
            </StatItem>
            <StatItem>
              <div className="icon" style={{backgroundColor: '#E6FFFA', color: '#38B2AC'}}><CheckCircle size={20}/></div>
              <div className="text">
                <span>98.7%</span>
                <p>성공률</p>
              </div>
            </StatItem>
          </TopBarStats>

          <TopBarActions>
            <RefreshButton onClick={handleRefreshKnowledge} disabled={syncing}>
              <RefreshCw size={16} />
              {syncing ? '갱신 중...' : '지식 베이스 갱신'}
            </RefreshButton>
            {/* 7. 닉네임/이니셜 동적 적용 및 /mypage로 이동 */}
            <UserProfile onClick={() => navigate('/mypage')}>
              <div className="avatar">{userInitials}</div>
              <div className="user-info">
                <span>{userNickname}</span>
                <ChevronDown size={18} />
              </div>
            </UserProfile>
          </TopBarActions>
        </TopBar>

        {syncMessage && (
          <SyncStatusBar $variant={syncMessage.variant}>
            {syncMessage.message}
          </SyncStatusBar>
        )}

        {/* 2.2 Chat Area & Analytics Area */}
        <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
          
          {/* 2.2.1 Chat Wrapper (Center) */}
          <ChatWrapper>
            <ChatContainer ref={chatContainerRef}>
              
              {/* 10. 채팅 메시지 렌더링 */}
              {chatMessages.length === 0 ? (
                <WelcomeMessage>
                  <h3>안녕하세요! Arcana AI Assistant입니다.</h3>
                  <p>조직의 모든 지식을 통합하여 맥락적 답변을 제공해드립니다. 무엇을 도와드릴까요? 예를 들어</p>
                  <ul>
                    <li>"지난 분기 고객 클레임 중 가장 큰 이슈는 무엇이었나?"</li>
                    <li>"프로젝트 Alpha의 기술적 결정사항과 근거를 정리해줘"</li>
                    <li>"마케팅팀의 Q4 전략 회의 내용을 요약해줘"</li>
                  </ul>
                </WelcomeMessage>
              ) : (
                chatMessages.map((msg, index) => (
                  <MessageWrapper key={index} $role={msg.role}>
                    <MessageHeader>
                      {msg.role === 'user' ? 'You' : 'Arcana AI'}
                    </MessageHeader>
                    {msg.role === 'user' ? (
                      <UserMessageBubble>{msg.content}</UserMessageBubble>
                    ) : (
                      <AIMessageBubble style={msg.isError ? {borderColor: '#FEB2B2', backgroundColor: '#FFF5F5'} : {}}>
                        {msg.content}
                        {/* 11. 소스 링크 및 복사 버튼 (에러 아닐 때) */}
                        {!msg.isError && (
                          <MessageToolbar>
                            {msg.sourcePage && (
                              <SourceLink href={msg.sourcePage} target="_blank" rel="noopener noreferrer">
                                출처: {msg.sourceId || 'Notion Page'}
                              </SourceLink>
                            )}
                            <CopyButton onClick={() => handleCopy(msg.content)}>
                              <Copy size={14} /> 복사
                            </CopyButton>
                          </MessageToolbar>
                        )}
                      </AIMessageBubble>
                    )}
                  </MessageWrapper>
                ))
              )}

              {/* 12. AI 응답 로딩 중 표시 */}
              {isChatLoading && (
                <MessageWrapper $role="ai">
                  <MessageHeader>Arcana AI</MessageHeader>
                  <LoadingDots>
                    <div />
                    <div />
                    <div />
                  </LoadingDots>
                </MessageWrapper>
              )}
            </ChatContainer>

            <ChatInputArea>
              <ChatTextarea
                ref={textareaRef} 
                placeholder="조직에서 궁금한 점들을 질문해보세요..."
                value={chatInput}
                onChange={handleTextareaChange}
                onKeyDown={handleKeyDown} 
                rows={1} 
                onCompositionStart={() => setIsComposing(true)} // 8. 한글 입력 시작
                onCompositionEnd={() => setIsComposing(false)} // 9. 한글 입력 완료
              />
              <ChatToolbar>
                <ToolbarLeft>
                  <Paperclip size={18} />
                  <Database size={18} />
                  <span>@</span>
                </ToolbarLeft>
                <ToolbarRight>
                  <span style={{fontSize: 12, color: '#718096'}}>Tokens 0/4000</span>
                  {/* 10. 전송 버튼 disabled 조건 추가 */}
                  <SendButton onClick={handleSendMessage} disabled={isChatLoading || isComposing}>
                    <Send size={16} />
                    전송
                  </SendButton>
                </ToolbarRight>
              </ChatToolbar>
            </ChatInputArea>
          </ChatWrapper>

          {/* 2.2.2 Analytics Sidebar (Right) */}
          <AnalyticsSidebar>
            <AnalyticsCard>
              <h3>ANALYTICS</h3>
              <NavItem><Activity size={18} /> AI 채팅 인터페이스</NavItem>
              <NavItem><FileText size={18} /> AI 채팅 인터페이스</NavItem>
            </AnalyticsCard>

            <AnalyticsCard>
              <h3>Knowledge Index</h3>
              <KnowledgeStat>
                <div className="icon"><Database size={24}/></div>
                <div className="text">
                  <span>2.4M</span>
                  <p>개선 현황</p>
                </div>
              </KnowledgeStat>
            </AnalyticsCard>

            <AnalyticsCard>
              <h3>활성화된 데이터소스</h3>
              {loadingConnections ? (
                <EmptyDataSource>로딩 중...</EmptyDataSource>
              ) : connections.length > 0 ? (
                connections.map(renderConnectionItem)
              ) : (
                <EmptyDataSource>
                  연결된 소스가 없습니다.
                </EmptyDataSource> 
              )}
            </AnalyticsCard>
          </AnalyticsSidebar>
        </div>
      </MainContent>

    </DashboardContainer>
  );
}

export default MainDashboard;