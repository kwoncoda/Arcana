sequenceDiagram
    %% 참가자 정의 (프론트, 백엔드, DB, 노션)
    participant Frontend as 프론트엔드
    participant Backend as 백엔드
    participant DB as 데이터베이스
    participant Notion as 노션 API

    %% ============== 1. 회원가입 프로세스 ==============
    Note over Frontend, DB: 1. 회원가입
    Frontend->>Backend: 회원가입 정보 전송 (ID, PW, 이메일 등)
    activate Backend
		
		%% 아직 중복은 확인하지 않음
    %% Backend->>DB: 사용자 정보 중복 확인 요청
    %% activate DB
    %% DB-->>Backend: 중복 확인 결과 반환
    %% deactivate DB

    alt 중복 또는 유효하지 않은 데이터
        Backend-->>Frontend: 에러 메시지 전송
    else 유효한 데이터
        Backend->>Backend: 비밀번호 해싱(암호화)
        Backend->>DB: 암호화된 사용자 정보 저장 요청
        activate DB
        DB-->>Backend: 저장 완료 응답
        deactivate DB
        Backend-->>Frontend: 회원가입 성공 응답
    end
    deactivate Backend

    %% ============== 2. 로그인 프로세스 ==============
    Note over Frontend, DB: 2. 로그인
    Frontend->>Backend: 로그인 정보 전송 (ID, PW)
    activate Backend
    
    Backend->>DB: ID로 사용자 정보(해시된 PW) 조회
    activate DB
    DB-->>Backend: 사용자 정보 반환
    deactivate DB
    
    Backend->>Backend: 입력된 PW 해싱 후 DB의 해시와 비교
    
    alt 인증 실패
        Backend-->>Frontend: 로그인 실패 메시지 전송
    else 인증 성공
        Backend->>Backend: JWT(인증 토큰) 생성
        Backend-->>Frontend: JWT 전송
        activate Frontend
        Frontend->>Frontend: 토큰 저장 및 로그인 페이지로 이동
        deactivate Frontend
    end
    deactivate Backend

    %% ============== 3. 노션 연동 프로세스 ==============
    Note over Frontend, Notion: 3. 노션 연동
    Frontend->>Frontend: 사용자가 '노션 연동' 버튼 클릭
    Frontend->>Notion: 인증 URL로 리디렉션
    activate Notion

    Notion-->>Frontend: 사용자가 페이지 선택 및 권한 허용
    Notion-->>Backend: 임시 인증 코드 발급
    deactivate Notion
    activate Backend

    Backend->>Notion: 액세스 토큰 요청 (인증 코드 + 시크릿)
    activate Notion
    Notion-->>Backend: 액세스 토큰 발급
    deactivate Notion
    
    Backend->>Notion: 토큰을 사용하여 페이지 데이터 요청
    activate Notion
    Notion-->>Backend: 페이지 데이터 반환
    deactivate Notion

    Note right of Backend: DB 저장 없이 실시간으로 RAG 시스템에 맞게 변환 및 적재
    Backend->>Backend: 데이터를 벡터로 변환 (Embedding)
    deactivate Backend


    %% ============== 4. 챗봇 (단순 대답) 프로세스 ==============
    Note over Frontend, Backend: 4. 챗봇 (단순 대답)
    Frontend->>Backend: 질문 전송 (String 타입)
    activate Backend
    
    Note right of Backend: LangGraph 워크플로우 시작
    
    loop 생성 및 자체 검증/개선
        Backend->>Backend: 1. 질문 의도 분석 (LLM 호출)
        Backend->>Backend: 2. 관련 정보 검색 (RAG)
        Backend->>Backend: 3. 초안 답변 생성 (LLM 호출)
        Backend->>Backend: 4. 답변 품질 평가
    end

    Backend-->>Frontend: 최종 답변 전송
    deactivate Backend
    
    activate Frontend
    Frontend->>Frontend: 화면에 답변 표시
    deactivate Frontend
