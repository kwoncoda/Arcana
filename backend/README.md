# Arcana Backend

## 프로젝트 개요
Arcana Backend는 조직용 지식 허브인 Arcana 서비스의 API 계층으로, FastAPI 기반 REST 엔드포인트를 통해 사용자 계정, 워크스페이스, 외부 데이터 소스 연동, RAG 검색 기능을 제공합니다.

## 소개
서비스는 단일 FastAPI 애플리케이션에 사용자 관리, Notion 데이터 수집, RAG 기반 답변 생성을 위한 라우터를 통합하고, 인증된 사용자의 워크스페이스 단위로 정보를 처리합니다. 모든 엔드포인트는 공통 CORS 설정과 헬스 체크를 제공하여 클라이언트 애플리케이션과의 연동을 단순화합니다.

## 상세 기능
### 1. 사용자 및 워크스페이스 관리
- PBKDF2-SHA256 기반 비밀번호 해시를 사용하여 회원 가입을 처리하고, 조직형 또는 개인형 워크스페이스를 자동으로 생성합니다.
- 로그인 시 액세스/리프레시 토큰을 발급하고, 만료된 리프레시 토큰을 검증하여 갱신 토큰을 재발급합니다.
- 워크스페이스 최초 생성 시 기본 RAG 인덱스 메타데이터와 스토리지를 보장합니다.

### 2. Notion 데이터 연동 및 적재
- Notion OAuth 플로우를 통해 사용자의 워크스페이스와 자격 증명을 초기화하고 연결 상태를 관리합니다.
- 공유된 Notion 페이지를 수집해 JSONL 레코드로 전처리한 뒤 LangChain 문서로 변환하고, 워크스페이스별 Chroma 벡터 스토어에 적재합니다.
- 적재 결과를 기반으로 RAG 인덱스 메타데이터(저장 경로, 청크 수 등)를 갱신합니다.

### 3. RAG 기반 검색 및 답변 생성
- 인증된 사용자의 기본 워크스페이스와 RAG 인덱스를 조회한 뒤, 비동기 실행으로 검색 에이전트를 호출합니다.
- Azure OpenAI Chat과 LangChain Runnable 체인을 사용해 컨텍스트 제한 응답을 생성하고, 최고 유사도 문서 URL을 답변 말미에 첨부합니다.
- Chroma 벡터 검색과 BM25 키워드 검색을 Reciprocal Rank Fusion으로 결합하여 하이브리드 검색을 제공합니다.

## 상세 기술
- **애플리케이션 프레임워크**: FastAPI와 Starlette를 사용하여 REST API와 비동기 워크플로우를 구성합니다.
- **데이터 계층**: SQLAlchemy ORM을 통해 사용자, 워크스페이스, 조직, RAG 인덱스, 데이터 소스 엔티티를 MySQL에 저장합니다.
- **검색 스택**: LangChain, Azure OpenAI 임베딩/챗 모델, Chroma 벡터 스토어, BM25 기반 키워드 인덱스를 조합한 하이브리드 검색을 구현합니다.
- **인증 및 보안**: JWT 기반 액세스/리프레시 토큰 발급과 검증, FastAPI 보안 의존성을 활용한 Bearer 토큰 보호를 제공합니다.
- **외부 연동**: Notion OAuth 및 API 호출을 위한 httpx 클라이언트, 공유 페이지 수집 및 토큰 갱신 로직을 포함합니다.

## 주요 구성요소
- **메인 애플리케이션** (`main.py`): 라우터 등록, CORS 설정, 헬스 체크 엔드포인트를 정의합니다.
- **사용자 라우터** (`routers/users.py`): 회원 가입, 로그인, 토큰 재발급 로직과 기본 RAG 인덱스 초기화를 담당합니다.
- **Notion 라우터** (`routers/notion.py`): OAuth 콜백, 데이터 소스 보장, 페이지 수집 및 RAG 적재를 제공합니다.
- **AI 에이전트 라우터 및 모듈** (`routers/aiagent.py`, `ai_module/rag_search.py`): 워크스페이스별 RAG 검색과 LLM 기반 답변 생성을 처리합니다
- **RAG 서비스** (`rag/chroma.py`): Azure OpenAI 임베딩, Chroma 스토어 캐싱, BM25 하이브리드 검색을 캡슐화합니다.
- **유틸리티** (`utils/`): DB 세션 팩토리, JWT 토큰 도우미, 워크스페이스 컨텍스트/스토리지 헬퍼를 포함합니다.

## 실행 전 준비
1. **필수 버전 및 패키지**: Python 3.10 이상과 `pyproject.toml`에 정의된 FastAPI, SQLAlchemy, LangChain, Chroma, httpx, notion-client 등의 의존성을 설치합니다.
2. **데이터베이스**: MySQL 인스턴스를 준비하고 연결 환경 변수(`MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_DATABASE`, `MYSQL_USER`, `MYSQL_PASSWORD`)를 설정합니다.
3. **JWT 설정**: `JWT_SECRET_KEY`, `JWT_ALGORITHM=HS256`, `JWT_ACCESS_TOKEN_EXPIRE_MINUTES`, `JWT_REFRESH_TOKEN_EXPIRE_DAYS` 환경 변수를 지정합니다.
4. **Azure OpenAI**: 챗 및 임베딩 모델용 API 키와 엔드포인트(`CM_*`, `EM_*`) 환경 변수를 설정합니다.
5. **Notion OAuth**: 클라이언트 ID/시크릿과 리디렉션 URI(`NOTION_CLIENT_ID`, `NOTION_CLIENT_SECRET`, `NOTION_REDIRECT_URI`)를 등록합니다
6. **RAG 검색 파라미터(선택)**: 검색 상한, 하이브리드 가중치 등을 조정하려면 `TOP_K`, `HYBRID_ALPHA`, `HYBRID_RRF_K` 환경 변수를 설정합니다.

## 실행 과정
1. 의존성 설치 후 데이터베이스 스키마를 초기화합니다. (예: Alembic 또는 수동 마이그레이션 스크립트를 사용해 `models/entities.py`에 정의된 테이블을 생성합니다).
2. 환경 변수를 로드한 상태에서 Uvicorn으로 FastAPI 애플리케이션을 실행합니다.
   ```bash
   cd backend
   uvicorn main:app --host 0.0.0.0 --port 8000
   ```
   Uvicorn이 `main.app` 인스턴스를 로드하여 사용자, Notion, AI 에이전트 라우터를 공개합니다.
3. `/api/health` 엔드포인트로 헬스 체크 후, `/api/users/*`, `/api/notion/*`, `/api/aiagent/search` 엔드포인트를 활용해 기능을 검증합니다.