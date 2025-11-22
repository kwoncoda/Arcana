# Arcana
조직 지식을 하나로 모으고 검색·생성까지 이어주는 AI 허브입니다. Notion과 Google Drive 같은 협업 도구를 연결해 RAG 기반 답변과 템플릿화된 문서를 만들어 줍니다.

## 목차
- [프로젝트 한눈에 보기](#프로젝트-한눈에-보기)
- [아키텍처](#아키텍처)
- [핵심 기능](#핵심-기능)
- [레포지토리 구조](#레포지토리-구조)
- [빠른 시작](#빠른-시작)
- [로컬 개발](#로컬-개발)
- [참고 문서](#참고-문서)

## 프로젝트 한눈에 보기
- **목표**: 분산된 협업 도구의 문서를 통합 검색하고, 근거가 포함된 답변과 문서 템플릿(회의 요약, 주간 리포트 등)을 생성합니다.
- **스택**: FastAPI + MySQL + Azure OpenAI/Chroma 기반 RAG, Vite/React 프런트엔드.
- **보안**: JWT 인증, 조직 단위 RAG 인덱스 격리, OAuth 토큰 암호화 저장을 지향합니다.
- **배포**: Docker Compose로 백엔드·프런트엔드·MySQL·Nginx를 한 번에 기동합니다.

## 아키텍처
- **backend**: FastAPI 서비스. 사용자/워크스페이스 관리, OAuth 콜백, RAG 검색 및 AI 에이전트 라우터를 제공합니다 (`backend/main.py`).
- **frontend**: Vite 기반 React 앱. OAuth 콜백과 대시보드/챗 UI를 제공하도록 구성되어 있습니다 (`frontend/my-react-app`).
- **database**: MySQL 8.4. 초기 스키마는 `init/init.sql`로 자동 적용됩니다.
- **proxy**: Nginx가 프런트엔드와 백엔드 트래픽을 80포트로 라우팅합니다.
- **storage**: 워크스페이스별 RAG 스토리지는 `workspace-storage` 볼륨에 마운트됩니다.

## 핵심 기능
### 사용자 & 워크스페이스
- 회원가입/로그인 시 PBKDF2-SHA256 해시와 JWT(액세스/리프레시) 발급을 수행합니다.
- 개인/조직형 워크스페이스를 생성하고 기본 RAG 인덱스 메타데이터를 보장합니다.

### 데이터 소스 연동
- **Notion**: OAuth로 공유 페이지를 수집해 JSONL/문서 형태로 변환 후 워크스페이스 RAG 스토어에 적재합니다.
- **Google Drive**: OAuth, 변경 스트림 기반 증분 동기화, 파일 스냅샷/메타데이터 관리, 재색인 판단 로직을 제공합니다 (`backend/routers/google_drive.py`).

### RAG 검색 및 생성형 응답
- LangChain Runnable과 Azure OpenAI 임베딩/챗 모델을 사용해 컨텍스트 제한 답변을 만듭니다.
- Chroma 벡터 검색과 BM25 키워드 검색을 결합한 하이브리드 검색을 지원합니다 (`backend/ai_module` 및 `backend/rag`).

### 프런트엔드
- React Router 기반 라우팅, axios 클라이언트, 토큰 인터셉터로 보호된 API 호출을 다룹니다.
- OAuth 콜백/대시보드/챗/마이페이지 등 주요 화면을 `frontend/my-react-app/src`에서 찾을 수 있습니다.

## 레포지토리 구조
- `backend/` — FastAPI 앱, 라우터(`routers/`), 모델(`models/`), AI/검색 모듈(`ai_module/`, `rag/`), Notion/Google Drive 유틸(`notions/`, `google_drive/`).
- `frontend/` — Vite + React 클라이언트 소스(`my-react-app/`)와 빌드용 Dockerfile.
- `init/` — MySQL 초기화 스크립트 및 시드 데이터.
- `docker-compose.yml` — MySQL·백엔드·프런트엔드·Nginx 서비스 정의와 볼륨 설정.
- `nginx.conf` — 리버스 프록시 및 정적 파일 서빙 설정.

## 빠른 시작
1. **환경 변수 준비**: `backend/.env` 파일을 생성해 아래 [필수 환경 변수](#필수-환경-변수)를 채웁니다.
2. **컨테이너 실행**:
   ```bash
   docker compose up --build
   ```
3. **확인**:
   - 백엔드: http://localhost:8000/api/docs (Swagger)
   - 프런트엔드: http://localhost:5173
   - 헬스 체크: `GET http://localhost:8000/api/health`

## 로컬 개발
- **백엔드 단독 실행**
  ```bash
  cd backend
  uv run uvicorn main:app --host 0.0.0.0 --port 8000 --reload
  ```
- **의존성 관리**: `uv`를 사용해 `pyproject.toml`/`uv.lock` 기반으로 설치합니다 (`uv pip sync` 또는 Dockerfile 참고).
- **데이터베이스**: 개발용 MySQL을 로컬에서 실행하거나 `docker compose up mysql`로 컨테이너만 띄운 뒤 `backend/.env`의 연결 정보를 맞춥니다.


## 참고 문서
- 백엔드 상세 기능 및 실행: [`backend/README.md`](backend/README.md)
- 초기 스키마: [`init/init.sql`](init/init.sql)
