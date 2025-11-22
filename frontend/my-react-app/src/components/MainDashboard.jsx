import React, { useState, useEffect, useCallback, useRef } from 'react';
import styled, { keyframes } from 'styled-components';
import { useNavigate, Link, useLocation } from 'react-router-dom';
import apiClient, { clearTokens, getAccessToken } from '../api/client';
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
  Square,
  Paperclip,
  Activity,
  FileText,
  AlertCircle,
  CheckCircle,
  HelpCircle,
  Brain,
  Copy,
  Menu, // [추가] 햄버거 아이콘
  X     // [추가] 닫기 아이콘
} from 'lucide-react';

// --- 스트리밍 효과를 위한 커스텀 훅 ---
function useInterval(callback, delay) {
  const savedCallback = useRef();

  useEffect(() => {
    savedCallback.current = callback;
  }, [callback]);

  useEffect(() => {
    function tick() {
      savedCallback.current();
    }
    if (delay !== null) {
      let id = setInterval(tick, delay);
      return () => clearInterval(id);
    }
  }, [delay]);
}


// --- Layout Containers ---

const DashboardContainer = styled.div`
  display: flex;
  width: 100%;
  height: 100vh;
  background-color: #F9FAFB;
  position: relative; /* 모바일 오버레이를 위해 relative */
`;

const spin = keyframes`
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
`;

// [수정] 모바일 반응형 사이드바 스타일 적용
const Sidebar = styled.nav`
  width: 260px;
  background-color: #1F2328; 
  color: #A0AEC0; 
  padding: 24px 16px;
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  transition: transform 0.3s ease-in-out;

  /* 모바일: 기본 숨김($isOpen false) -> 슬라이드 등작($isOpen true) */
  @media (max-width: 768px) {
    position: fixed;
    top: 0;
    left: 0;
    height: 100vh;
    z-index: 1000;
    transform: ${({ $isOpen }) => ($isOpen ? 'translateX(0)' : 'translateX(-100%)')};
    box-shadow: ${({ $isOpen }) => ($isOpen ? '4px 0 15px rgba(0,0,0,0.5)' : 'none')};
  }
`;

// [추가] 모바일 오버레이 (배경 어둡게)
const MobileOverlay = styled.div`
  display: none;
  @media (max-width: 768px) {
    display: ${({ $isOpen }) => ($isOpen ? 'block' : 'none')};
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background-color: rgba(0, 0, 0, 0.5);
    z-index: 999;
  }
`;

const SyncingOverlay = styled.div`
  position: fixed;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.55);
  opacity: ${({ $visible }) => ($visible ? 1 : 0)};
  pointer-events: ${({ $visible }) => ($visible ? 'auto' : 'none')};
  transition: opacity 0.2s ease;
  z-index: 1200;
`;

const ChatLoadingOverlay = styled(SyncingOverlay)`
  z-index: 1250;
`;

const SyncingCard = styled.div`
  min-width: 280px;
  background: #ffffff;
  border-radius: 12px;
  padding: 20px 24px;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.18);
  display: flex;
  align-items: center;
  gap: 14px;
`;

const ChatLoadingCard = styled(SyncingCard)`
  max-width: 420px;
  width: 90%;
  text-align: center;
`;

const SyncingSpinner = styled.div`
  width: 32px;
  height: 32px;
  border: 3px solid #e2e8f0;
  border-top-color: #4a5568;
  border-radius: 50%;
  aspect-ratio: 1 / 1;
  animation: ${spin} 0.9s linear infinite;
`;

const SyncingTextGroup = styled.div`
  display: flex;
  flex-direction: column;
  gap: 4px;

  strong {
    font-size: 15px;
    color: #1a202c;
  }

  span {
    font-size: 13px;
    color: #4a5568;
  }
`;

const ChatOverlayActions = styled.div`
  display: flex;
  justify-content: center;
  margin-left: auto;
  margin-right: auto;
`;

const ChatOverlayButton = styled.button`
  margin-top: 8px;
  padding: 10px 16px;
  background-color: #F56565;
  color: #fff;
  border: 1px solid #E53E3E;
  border-radius: 8px;
  font-weight: 600;
  cursor: pointer;
  transition: background-color 0.2s ease, color 0.2s ease;

  &:hover {
    background-color: #E53E3E;
    color: #fff;
  }

  &:active {
    background-color: #C53030;
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

// [추가] 모바일 메뉴 버튼
const MobileMenuBtn = styled.button`
  display: none;
  background: none;
  border: none;
  cursor: pointer;
  color: #4A5568;
  margin-right: 12px;
  padding: 4px;

  @media (max-width: 768px) {
    display: flex;
    align-items: center;
    justify-content: center;
  }
`;

// [추가] 상단 좌측 그룹 (메뉴 버튼 + 헤더)
const TopBarLeftGroup = styled.div`
  display: flex;
  align-items: center;
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

  /* 모바일에서는 텍스트 숨김 */
  @media (max-width: 500px) {
    span {
      display: none;
    }
    padding: 8px;
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
  min-width: 0;
`;

const AnalyticsSidebar = styled.aside`
  width: 320px;
  flex-shrink: 0;
  background-color: #F9FAFB;
  padding: 24px;
  overflow-y: auto;
  border-left: 1px solid #E2E8F0;

  @media (max-width: 1280px) {
    display: none;
  }
`;


// --- Sidebar Components ---

// [추가] 사이드바 헤더 (로고 + 닫기 버튼)
const SidebarHeaderRow = styled.div`
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
  padding: 0 8px;
`;

// [추가] 사이드바 닫기 버튼
const SidebarCloseBtn = styled.button`
  display: none;
  background: none;
  border: none;
  color: #A0AEC0;
  cursor: pointer;
  
  @media (max-width: 768px) {
    display: block;
  }
`;

const LogoHeader = styled.div`
  /* SidebarHeaderRow 사용으로 인해 margin 제거 */
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
  justify-content: space-between;
  gap: 12px;
`;

const DataSourceInfo = styled.div`
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;

  /* 아이콘만 스타일 */
  > span:first-child {
    width: 20px;
    height: 20px;
    border-radius: 4px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 12px;
    font-weight: 700;
    flex-shrink: 0;
  }

  /* 라벨은 남은 폭을 차지하며 줄임표 */
  > span:last-child {
    flex: 1;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
`;

const DisconnectButton = styled.button`
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border-radius: 6px;
  border: none;
  background: transparent;
  color: #CBD5E0;
  cursor: pointer;
  transition: background-color 0.2s ease, color 0.2s ease;

  &:hover {
    background: rgba(255, 255, 255, 0.05);
    color: #F56565;
  }

  &:disabled {
    opacity: 0.6;
    cursor: not-allowed;
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

    @media (max-width: 500px) {
      display: none;
    }
  }
`;

const TopBarStats = styled.div`
  display: flex;
  align-items: center;
  gap: 24px;

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
  word-wrap: break-word;
`;

const UserMessageBubble = styled(MessageBubble)`
  background-color: #6200EE;
  color: white;
  border-top-right-radius: 0;
  line-height: 1.6;
  white-space: pre-wrap;
`;

const AIMessageBubble = styled(MessageBubble)`
  background-color: #F7F7F9;
  color: #1A202C;
  border: 1px solid #E2E8F0;
  border-top-left-radius: 0;
  position: relative;
`;

const AIMessageContent = styled.div`
  font-size: 14px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-wrap: break-word;
`;

const StyledHr = styled.hr`
  border: none;
  border-top: 1px solid #E2E8F0;
  margin: 12px 0;
`;

const MessageToolbar = styled.div`
  display: flex;
  justify-content: flex-end;
  align-items: center;
  margin-top: 8px;
  gap: 16px;
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
  margin-right: auto;
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
  background-color: ${({ $variant }) => ($variant === 'stop' ? '#E53E3E' : '#6200EE')};
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
    background-color: ${({ $variant }) => ($variant === 'stop' ? '#C53030' : '#5100C4')};
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

const getDisconnectEndpoint = (connection) => {
  const providerKey = (connection?.type || connection?.name || '').toLowerCase();

  if (providerKey === 'notion') return '/api/notion/disconnect';
  if (providerKey === 'googledrive' || providerKey === 'google-drive' || providerKey === 'google_drive') {
    return '/api/google-drive/disconnect';
  }

  return null;
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

const getInitials = (name) => {
  if (!name) return 'U';
  const parts = name.trim().split(' ');
  if (parts.length > 1 && parts[parts.length - 1]) {
    return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
  }
  return name[0].toUpperCase();
};

// --- 스트리밍 메시지 컴포넌트 ---
const StreamingAIMessage = ({ content, sourcePage, sourceId, isError, onCopy, onStreamUpdate }) => {
  const [displayedText, setDisplayedText] = useState('');
  const [isComplete, setIsComplete] = useState(false);
  const streamDelay = 30;

  useInterval(() => {
    if (isComplete || isError) {
      return;
    }

    if (displayedText.length < content.length) {
      setDisplayedText(content.substring(0, displayedText.length + 1));
    } else {
      setIsComplete(true);
    }
  }, streamDelay);

  useEffect(() => {
    if (isError) {
      setDisplayedText(content);
      setIsComplete(true);
    }
  }, [isError, content]);

  useEffect(() => {
    if (onStreamUpdate) {
      onStreamUpdate();
    }
  }, [displayedText, onStreamUpdate]);

  return (
    <AIMessageBubble style={isError ? {borderColor: '#FEB2B2', backgroundColor: '#FFF5F5'} : {}}>
      <AIMessageContent>
        {displayedText}
        {!isComplete && !isError && <span className="cursor" style={{borderRight: '2px solid #6200EE', marginLeft: '2px', animation: 'blink 1s step-end infinite'}}></span>}
      </AIMessageContent>
      
      {isComplete && !isError && (sourcePage || content) && (
        <>
          <StyledHr />
          <MessageToolbar>
            {sourcePage && (
              <SourceLink href={sourcePage} target="_blank" rel="noopener noreferrer">
                출처: {sourceId || 'Notion Page'}
              </SourceLink>
            )}
            <CopyButton onClick={() => onCopy(content)}>
              <Copy size={14} /> 복사
            </CopyButton>
          </MessageToolbar>
        </>
      )}
    </AIMessageBubble>
  );
};


// --- React Component ---

function MainDashboard() {
  const [chatInput, setChatInput] = useState('');
  const [connections, setConnections] = useState([]);
  const [loadingConnections, setLoadingConnections] = useState(true);
  const [disconnectingSource, setDisconnectingSource] = useState(null);
  const [syncing, setSyncing] = useState(false);
  const [syncMessage, setSyncMessage] = useState(null);
  const [shouldAutoRefresh, setShouldAutoRefresh] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();

  // 닉네임/이니셜 state
  const [userNickname, setUserNickname] = useState('User');
  const [userInitials, setUserInitials] = useState('U');

  const [chatMessages, setChatMessages] = useState([]);
  const [isChatLoading, setIsChatLoading] = useState(false);
  const [isAutoScrollEnabled, setIsAutoScrollEnabled] = useState(true);
  const chatContainerRef = useRef(null);
  const textareaRef = useRef(null);
  const chatRequestControllerRef = useRef(null);
  
  // [추가] 모바일 사이드바 상태
  const [isMobileSidebarOpen, setIsMobileSidebarOpen] = useState(false);

  const scrollToBottom = useCallback(() => {
    if (chatContainerRef.current) {
      chatContainerRef.current.scrollTop = chatContainerRef.current.scrollHeight;
    }
  }, []);

  const handleStreamUpdate = useCallback(() => {
    if (isAutoScrollEnabled) {
      scrollToBottom();
    }
  }, [isAutoScrollEnabled, scrollToBottom]);

  const fetchConnections = useCallback(async (tokenOverride) => {
    setLoadingConnections(true);
    try {
      const token = tokenOverride || getAccessToken();
      if (!token) {
        navigate('/login');
        return [];
      }

      const res = await apiClient.get('/api/users/connections');

      const fetchedConnections = res.data.connections || [];
      setConnections(fetchedConnections);
      return fetchedConnections;
    } catch (err) {
      console.error('Failed to fetch connections:', err);
      const status = err?.response?.status;
      if (status === 401 || status === 404) {
        clearTokens();
        localStorage.removeItem('userNickname');
        navigate('/login');
      }
      throw err;
    } finally {
      setLoadingConnections(false);
    }
  }, [navigate]);

  useEffect(() => {
    const nickname = localStorage.getItem('userNickname');
    if (nickname) {
      setUserNickname(nickname);
      setUserInitials(getInitials(nickname));
    }

    fetchConnections().catch(() => {});
  }, [fetchConnections]);

  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const connected = params.get('connected');
    const source = params.get('source');
    const syncFailed = params.get('syncFailed') === '1';

    if (connected && source) {
      if (source === 'notion') {
        setSyncMessage({
          variant: syncFailed ? 'warning' : 'success',
          message: syncFailed
            ? '노션 연동은 완료되었지만 지식 베이스 갱신 중 오류가 발생했습니다. 다시 시도해주세요.'
            : '노션이 연동되었습니다.',
        });
      } else if (source === 'google-drive') {
        setSyncMessage({
          variant: syncFailed ? 'warning' : 'success',
          message: syncFailed
            ? 'Google Drive 연동은 완료되었지만 지식 베이스 갱신 중 오류가 발생했습니다. 다시 시도해주세요.'
            : 'Google Drive가 연동되었습니다.',
        });
      }

      setShouldAutoRefresh(true);

      navigate(location.pathname, { replace: true, state: {} });
    }
  }, [location, navigate]);

  useEffect(() => {
    if (location.state?.notionConnected) {
      setSyncMessage({
        variant: location.state.notionSyncFailed ? 'warning' : 'success',
        message: location.state.notionSyncFailed
          ? '노션 연동은 완료되었지만 지식 베이스 갱신 중 오류가 발생했습니다. 다시 시도해주세요.'
          : '노션이 연동되었습니다.',
      });
      setShouldAutoRefresh(true);
      navigate(location.pathname, { replace: true, state: {} });
      return;
    }

    if (location.state?.googleConnected) {
      setSyncMessage({
        variant: location.state.googleSyncFailed ? 'warning' : 'success',
        message: location.state.googleSyncFailed
          ? 'Google Drive 연동은 완료되었지만 지식 베이스 갱신 중 오류가 발생했습니다. 다시 시도해주세요.'
          : 'Google Drive가 연동되었습니다.',
      });
      setShouldAutoRefresh(true);
      navigate(location.pathname, { replace: true, state: {} });
    }
  }, [location, navigate]);

  const handleRefreshKnowledge = useCallback(async () => {
    if (syncing) return;

    const token = getAccessToken();
    if (!token) {
      setSyncMessage({
        variant: 'error',
        message: '로그인이 필요합니다. 다시 로그인해주세요.'
      });
      navigate('/login');
      return;
    }

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

        if (type === 'notion' || type === 'google-drive') {
          let pullEndpoint = '';
          if (type === 'notion') {
            pullEndpoint = '/api/notion/pages/pull';
          } else if (type === 'google-drive') {
            pullEndpoint = '/api/google-drive/files/pull';
          }

          try {
            const response = await apiClient.post(pullEndpoint, {});
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
              clearTokens();
              localStorage.removeItem('userNickname');
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
  }, [connections, fetchConnections, navigate, syncing]);

  const handleSendMessage = async () => {
    const query = chatInput.trim();
    if (!query || isChatLoading) return;

    const controller = new AbortController();
    chatRequestControllerRef.current = controller;
    setIsChatLoading(true);
    setChatInput('');
    if (textareaRef.current) {
      autoResizeTextarea(textareaRef.current);
    }

    const token = getAccessToken();
    if (!token) {
      navigate('/login');
      return;
    }

    setChatMessages((prev) => [...prev, { role: 'user', content: query }]);

    try {
      const res = await apiClient.post(
        '/api/aiagent/search',
        { query },
        {
          signal: controller.signal,
        }
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
      if (err.code === 'ERR_CANCELED') {
        return;
      }
      console.error('AI Search Error:', err);
      let errorMessage = '답변을 생성하는 중 오류가 발생했습니다.';
      if (err.response) {
        if (err.response.status === 401) {
          clearTokens();
          localStorage.removeItem('userNickname');
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
      chatRequestControllerRef.current = null;
    }
  };

  useEffect(() => {
    if (shouldAutoRefresh && !syncing) {
      setShouldAutoRefresh(false);
      handleRefreshKnowledge();
    }
  }, [handleRefreshKnowledge, shouldAutoRefresh, syncing]);

  useEffect(() => {
    if (isAutoScrollEnabled) {
      scrollToBottom();
    }
  }, [chatMessages, isChatLoading, isAutoScrollEnabled, scrollToBottom]);

  useEffect(() => {
    const container = chatContainerRef.current;
    if (!container) return;

    const handleScroll = () => {
      const { scrollTop, scrollHeight, clientHeight } = container;
      const isAtBottom = Math.abs(scrollHeight - scrollTop - clientHeight) < 10;
      setIsAutoScrollEnabled(isAtBottom);
    };

    container.addEventListener('scroll', handleScroll);
    return () => {
      container.removeEventListener('scroll', handleScroll);
    };
  }, []);

  const autoResizeTextarea = (element) => {
    element.style.height = 'auto';
    element.style.height = `${element.scrollHeight}px`;
  };

  const handleTextareaChange = (e) => {
    setChatInput(e.target.value);
    autoResizeTextarea(e.target);
  };

  // [수정] 로그아웃 로직 제거 (MyPage에서 처리)

  // [추가] 사이드바 토글 함수
  const toggleMobileSidebar = () => {
    setIsMobileSidebarOpen(!isMobileSidebarOpen);
  };

  // [추가] 사이드바 메뉴 클릭 시 닫기
  const handleNavClick = () => {
    if (window.innerWidth <= 768) {
      setIsMobileSidebarOpen(false);
    }
  };

  const handleStopMessage = () => {
    if (chatRequestControllerRef.current) {
      chatRequestControllerRef.current.abort();
      chatRequestControllerRef.current = null;
    }
    setIsChatLoading(false);
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

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

  const handleDisconnectConnection = async (event, connection) => {
    event?.stopPropagation?.();

    const details = getProviderDetails(connection);
    const endpoint = getDisconnectEndpoint(connection);

    if (!endpoint) {
      setSyncMessage({
        variant: 'warning',
        message: `${details.name} 데이터 소스는 아직 연결 해제를 지원하지 않습니다.`,
      });
      return;
    }

    const confirmMessage = `${details.name} 데이터 소스 연결을 끊으시겠습니까?`;
    const shouldDisconnect = window.confirm(confirmMessage);
    if (!shouldDisconnect) return;

    const token = getAccessToken();
    if (!token) {
      navigate('/login');
      return;
    }

    try {
      setDisconnectingSource(connection?.type || details.name);
      await apiClient.post(endpoint, {});

      await fetchConnections(token);
    } catch (err) {
      console.error('Failed to disconnect data source:', err);
      const status = err?.response?.status;
      if (status === 401 || status === 404) {
        clearTokens();
        localStorage.removeItem('userNickname');
        navigate('/login');
        return;
      }

      const detail = err?.response?.data?.detail;
      setSyncMessage({
        variant: 'error',
        message: detail
          ? `연결 해제에 실패했습니다: ${detail}`
          : '연결 해제에 실패했습니다. 잠시 후 다시 시도해주세요.',
      });
    } finally {
      setDisconnectingSource(null);
    }
  };

  const renderConnectionItem = (conn) => {
    const details = getProviderDetails(conn);
    const itemKey = conn.type || details.name;
    const isDisconnecting = disconnectingSource === itemKey;

    if (conn.status === 'connected' || conn.connected === true) {
      return (
        <DataSourceItem key={itemKey}>
          <DataSourceInfo>
            <span style={{ color: details.color, backgroundColor: details.bg }}>
              {details.icon}
            </span>
            <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {details.name}
            </span>
          </DataSourceInfo>
          <DisconnectButton
            aria-label={`${details.name} 연결 끊기`}
            title="연결 끊기"
            onClick={(event) => handleDisconnectConnection(event, conn)}
            disabled={isDisconnecting}
          >
            {isDisconnecting ? '…' : <X size={14} />}
          </DisconnectButton>
        </DataSourceItem>
      );
    }
    return null;
  };

  return (
    <DashboardContainer>

      <ChatLoadingOverlay $visible={isChatLoading}>
        <ChatLoadingCard>
          <SyncingSpinner />
          <SyncingTextGroup>
            <strong>답변 중입니다</strong>
            <span>잠시만 기다려주세요.</span>
          </SyncingTextGroup>
          <ChatOverlayActions>
            <ChatOverlayButton type="button" onClick={handleStopMessage}>
              중지
            </ChatOverlayButton>
          </ChatOverlayActions>
        </ChatLoadingCard>
      </ChatLoadingOverlay>

      <SyncingOverlay $visible={syncing}>
        <SyncingCard>
          <SyncingSpinner />
          <SyncingTextGroup>
            <strong>지식 베이스를 갱신하고 있습니다</strong>
            <span>데이터 소스 동기화가 끝날 때까지 잠시만 기다려주세요.</span>
          </SyncingTextGroup>
        </SyncingCard>
      </SyncingOverlay>

      {/* [추가] 모바일 오버레이 */}
      <MobileOverlay $isOpen={isMobileSidebarOpen} onClick={toggleMobileSidebar} />

      {/* [수정] Sidebar에 isOpen prop 전달 */}
      <Sidebar $isOpen={isMobileSidebarOpen}>
        {/* [추가] 사이드바 헤더 로우 (로고 + 닫기 버튼) */}
        <SidebarHeaderRow>
          <LogoText><Brain size={24} /> Arcana</LogoText>
          <SidebarCloseBtn onClick={toggleMobileSidebar}>
            <X size={24} />
          </SidebarCloseBtn>
        </SidebarHeaderRow>

        <LogoHeader>
          <Subtitle>정보 파편화의 해결자 플랫폼</Subtitle>
        </LogoHeader>

        <NavMenu>
          <SectionTitle>MAIN DASHBOARD</SectionTitle>
          {/* [수정] 모바일에서 클릭 시 사이드바 닫히도록 handleNavClick 추가 */}
          <NavItem onClick={handleNavClick}><Home size={18} /> 메인화면</NavItem>
          <NavItem onClick={handleNavClick}><MessageSquare size={18} /> AI 채팅 인터페이스</NavItem>

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

          <NavItem as={Link} to="/connect/notion" onClick={handleNavClick}>
            <Plus size={18} /> Add more sources
          </NavItem>
        </NavMenu>

        <UpgradeBanner>
          <UpgradeText>
            프로 요금제의 저장 공간이 거의 다 찼습니다. 프리미엄 요금제로 업그레이드하세요.
          </UpgradeText>
        </UpgradeBanner>
      </Sidebar>

      <MainContent>
        <TopBar>
          <TopBarLeftGroup>
            {/* [추가] 햄버거 메뉴 버튼 */}
            <MobileMenuBtn onClick={toggleMobileSidebar}>
              <Menu size={24} />
            </MobileMenuBtn>
            <TopBarHeader>
              <h2>Arcana AI 정보 어시턴트</h2>
              <p>조직의 지식에 기반하여 궁금증을 질문해보세요</p>
            </TopBarHeader>
          </TopBarLeftGroup>

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
              <span>{syncing ? '갱신 중...' : '지식 베이스 갱신'}</span>
            </RefreshButton>
            {/* [수정] 마이페이지로 이동 */}
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

        <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
          
          <ChatWrapper>
            <ChatContainer ref={chatContainerRef}>
              
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
                      <StreamingAIMessage
                        content={msg.content}
                        sourcePage={msg.sourcePage}
                        sourceId={msg.sourceId}
                        isError={msg.isError}
                        onCopy={handleCopy}
                        onStreamUpdate={handleStreamUpdate}
                      />
                    )}
                  </MessageWrapper>
                ))
              )}

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
              />
              <ChatToolbar>
                <ToolbarLeft>
                  <Paperclip size={18} />
                  <Database size={18} />
                  <span>@</span>
                </ToolbarLeft>
                <ToolbarRight>
                  <span style={{fontSize: 12, color: '#718096'}}>Tokens 0/4000</span>
                  <SendButton
                    onClick={isChatLoading ? handleStopMessage : handleSendMessage}
                    $variant={isChatLoading ? 'stop' : 'send'}
                  >
                    {isChatLoading ? <Square size={16} /> : <Send size={16} />}
                    {isChatLoading ? '정지' : '전송'}
                  </SendButton>
                </ToolbarRight>
              </ChatToolbar>
            </ChatInputArea>
          </ChatWrapper>

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