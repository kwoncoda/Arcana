import React, { useState } from 'react';
import styled from 'styled-components';
import { useNavigate } from 'react-router-dom';
import { 
  Home, 
  MessageSquare, 
  Database, 
  Settings, 
  Plus, 
  ChevronDown, 
  User, 
  Send, 
  Paperclip,
  Activity,
  FileText,
  AlertCircle,
  CheckCircle,
  HelpCircle,
  Brain
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

  /* --- 768px 이하 숨김 --- */
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

  /* --- 1280px 이하 숨김 --- */
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

  &:hover {
    background-color: #2D3748;
  }

  /* ${(props) =>
    props.$active &&
    `
    background-color: #4A5568;
    color: #FFFFFF;
  `}
  */
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
  
  /* 500px 이하 숨김 */
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

// 웰컴 메시지
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
  min-height: 60px;
  font-family: inherit;

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


// --- Mock Data ---
const dataSources = [
  { name: 'Slack', icon: 'S', color: '#4A154B', bg: '#EFE1EF' },
  { name: 'Notion', icon: 'N', color: '#000000', bg: '#E0E0E0' },
  { name: 'Jira', icon: 'J', color: '#0052CC', bg: '#DEEBFF' },
  { name: 'Google Cloud', icon: 'G', color: '#4285F4', bg: '#E8F0FE' },
  { name: 'Figma', icon: 'F', color: '#F24E1E', bg: '#FCECEA' },
];

// --- React Component ---

function MainDashboard() {
  const [chatInput, setChatInput] = useState('');
  const navigate = useNavigate();

  const handleLogout = () => {
    // 실제 로그아웃 시 토큰 제거
    // localStorage.removeItem('accessToken');
    // localStorage.removeItem('refreshToken');
    navigate('/login');
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
          {/* 요청하신 대로 2개 삭제 */}

          <SectionTitle>DATA SOURCES</SectionTitle>
          {dataSources.map(src => (
            <DataSourceItem key={src.name}>
              <span style={{ color: src.color, backgroundColor: src.bg }}>{src.icon}</span>
              {src.name}
            </DataSourceItem>
          ))}
          <NavItem><Plus size={18} /> Add more sources</NavItem>
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

          <UserProfile onClick={handleLogout}>
            <div className="avatar">AK</div>
            <div className="user-info"> 
              <span>Aiden Kim</span>
              <ChevronDown size={18} />
            </div>
          </UserProfile>
        </TopBar>

        {/* 2.2 Chat Area & Analytics Area */}
        <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
          
          {/* 2.2.1 Chat Wrapper (Center) */}
          <ChatWrapper>
            <ChatContainer>
              {/* 채팅이 비어있을 때 표시되는 웰컴 메시지 */}
              <WelcomeMessage>
                <h3>안녕하세요! Arcana AI Assistant입니다.</h3>
                <p>조직의 모든 지식을 통합하여 맥락적 답변을 제공해드립니다. 무엇을 도와드릴까요? 예를 들어</p>
                <ul>
                  <li>"지난 분기 고객 클레임 중 가장 큰 이슈는 무엇이었나?"</li>
                  <li>"프로젝트 Alpha의 기술적 결정사항과 근거를 정리해줘"</li>
                  <li>"마케팅팀의 Q4 전략 회의 내용을 요약해줘"</li>
                </ul>
              </WelcomeMessage>
            </ChatContainer>

            <ChatInputArea>
              <ChatTextarea
                placeholder="조직에서 궁금한 점들을 질문해보세요..."
                value={chatInput}
                onChange={(e) => setChatInput(e.target.value)}
                rows={3}
              />
              <ChatToolbar>
                <ToolbarLeft>
                  <Paperclip size={18} />
                  <Database size={18} />
                  <span>@</span>
                </ToolbarLeft>
                <ToolbarRight>
                  <span style={{fontSize: 12, color: '#718096'}}>Tokens 0/4000</span>
                  <SendButton>
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
              {/* 요청하신 대로 2개 삭제 */}
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
              <DataSourceItem>
                <span style={{ color: dataSources[0].color, backgroundColor: dataSources[0].bg }}>{dataSources[0].icon}</span>
                {dataSources[0].name}
              </DataSourceItem>
              <DataSourceItem>
                <span style={{ color: dataSources[1].color, backgroundColor: dataSources[1].bg }}>{dataSources[1].icon}</span>
                {dataSources[1].name}
              </DataSourceItem>
            </AnalyticsCard>

          </AnalyticsSidebar>
        </div>
      </MainContent>

    </DashboardContainer>
  );
}

export default MainDashboard;

