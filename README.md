# Arcana

## 프로젝트 개요
Arcana는 사내 문서와 외부 지식원을 연결해 검색과 생성형 답변을 제공하기 위한 AI 어시스턴트 플랫폼입니다. FastAPI 백엔드와 MySQL 데이터베이스를 Docker Compose로 손쉽게 구동할 수 있으며, Notion OAuth 연동과 RAG 인덱스를 고려한 데이터 모델을 제공합니다.

## 소개
- **백엔드**: 사용자 인증과 Notion 연동을 담당하는 FastAPI 애플리케이션으로, Swagger 문서를 통해 기본 상태 점검(health check)과 사용자 API를 제공합니다.
- **데이터 계층**: 초기 스키마는 사용자, 조직, 워크스페이스, RAG 인덱스, 데이터 소스, OAuth 토큰 및 동기화 상태 테이블을 포함하며 Notion 기반 데이터 취득과 색인화를 염두에 두고 설계되었습니다.
- **배포 환경**: Docker Compose로 MySQL 8.4와 백엔드를 한 번에 띄울 수 있도록 구성되어 있으며, 초기화 스크립트는 `init/init.sql`을 통해 자동 실행됩니다.

## 상세 기능
1. **사용자 관리**
   - 회원 가입: 사용자 ID, 이메일, 닉네임 중복을 검증하고 PBKDF2 해시로 비밀번호를 안전하게 저장합니다.
   - 로그인: 사용자 활성 여부를 확인하고 Access/Refresh JWT 토큰을 발급하며 마지막 로그인 시각을 기록합니다.
2. **인증 토큰 발급**
   - HMAC-SHA256을 사용한 커스텀 JWT 생성 로직으로 Access/Refresh 토큰 만료 시간을 개별 설정할 수 있습니다.
3. **데이터베이스 액세스**
   - 환경 변수 기반의 MySQL 연결 정보를 생성하고 SQLAlchemy 세션 팩토리를 제공합니다.
4. **Notion OAuth 준비**
   - Notion OAuth 로그인, 토큰 저장, 페이지 동기화 등을 위한 헬퍼가 포함되어 있으며 FastAPI 라우터 등록만으로 확장 가능합니다.
5. **헬스 체크**
   - `/api/health` 엔드포인트를 통해 서비스 가용성을 확인할 수 있습니다.

## 상세 기술
| 영역 | 사용 기술 | 비고 |
| --- | --- | --- |
| 웹 프레임워크 | FastAPI | Swagger를 통한 자동 문서화, 라우터 기반 모듈화 |
| 인증 | 커스텀 JWT(HMAC-SHA256), PBKDF2-SHA256 | 환경 변수로 비밀키/만료시간 제어 |
| 데이터베이스 | MySQL 8.4, SQLAlchemy ORM | Docker Compose와 초기화 스크립트 연동 |
| 외부 연동 | Notion OAuth, notion-client SDK | 토큰 저장용 SQLAlchemy 모델 포함 |
| 컨테이너 | Docker, Docker Compose, uv 패키지 매니저 | Hot reload 설정된 uvicorn 실행 |

## 주요 구성요소
- `backend/main.py`: FastAPI 앱 초기화, 사용자 라우터 등록, 헬스 체크 엔드포인트 정의.
- `backend/routers/users.py`: 사용자 모델 정의와 `/users/register`, `/users/login` REST API 구현.
- `backend/schema/users.py`: 회원 가입/로그인 요청 및 응답 스키마 정의.
- `backend/utils/`: 데이터베이스 연결(`db.py`)과 JWT 유틸리티(`auth.py`).
- `backend/notions/`: Notion OAuth 플로우, 토큰 저장 모델, 페이지 조회 유틸리티.
- `init/init.sql`: 서비스 구동 시 자동 생성되는 MySQL 테이블 스키마 정의.
- `docker-compose.yml`: MySQL과 백엔드 컨테이너 오케스트레이션, 초기 스크립트 마운트 설정.

## 실행 전 준비
1. **필수 도구**
   - Docker 24+ 및 Docker Compose v2 이상.
2. **환경 변수 파일(`backend/.env`) 작성**
   - MySQL 연결 정보
     ```env
     MYSQL_HOST=mysql
     MYSQL_PORT=3306
     MYSQL_DATABASE=arcana
     MYSQL_USER=arcana
     MYSQL_PASSWORD=<사용자 비밀번호>
     MYSQL_ROOT_PASSWORD=<루트 비밀번호>
     ```
   - JWT 설정
     ```env
     JWT_SECRET_KEY=<32자 이상 랜덤 시크릿>
     JWT_ALGORITHM=HS256
     JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
     JWT_REFRESH_TOKEN_EXPIRE_DAYS=14
     ```
   - Notion OAuth (사용 시)
     ```env
     NOTION_CLIENT_ID=<Notion Integration ID>
     NOTION_CLIENT_SECRET=<Notion Secret>
     NOTION_REDIRECT_URI=http://localhost:8000/oauth/callback
     ```
   - `.env`는 `docker-compose.yml`의 `env_file`로 두 컨테이너에 주입됩니다.

## 실행 과정
1. 프로젝트 루트에서 컨테이너 이미지 빌드 및 서비스 기동
   ```bash
   docker compose up --build
   ```
2. MySQL 컨테이너가 `init/init.sql`을 실행하여 기본 스키마를 생성합니다.
3. 백엔드 컨테이너는 `uvicorn`을 통해 8000번 포트에서 FastAPI 앱을 구동합니다.
4. 브라우저에서 `http://localhost:8000/api/docs`에 접속하면 Swagger UI를 통해 API를 테스트할 수 있습니다.
5. `/api/users/register`, `/api/users/login`, `/api/health` 엔드포인트를 활용해 사용자 흐름과 상태를 점검합니다.

## 추가 안내
- **DB 마이그레이션**: 현재는 초기 스키마만 제공되므로, 변경이 필요한 경우 `init/init.sql`을 수정하거나 Alembic 등의 마이그레이션 도구 도입을 권장합니다.
- **보안**: JWT 시크릿과 데이터베이스 비밀번호는 운영 환경에서 비밀 관리 시스템(예: AWS Secrets Manager, Vault)에 저장하세요.
- **Notion 연동 활성화**: `backend/main.py`에서 주석 처리된 Notion 라우터를 해제하면 OAuth 플로우와 페이지 동기화 API를 사용할 수 있습니다.
