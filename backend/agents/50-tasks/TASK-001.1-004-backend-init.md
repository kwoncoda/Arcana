---
id: TASK-0001
type: task
title: backend 폴더 생성 및 uv init으로 가상환경 구성
status: done
owner: backend
updated: 2025-09-22
artifacts:
  - code: /README.md
  - script: /backend/pyproject.toml
---
## DoD
- backend 디렉터리 생성 및 uv 환경 초기화 완료
- 의존성 설치/실행 확인 로그 남김

---
id: TASK-0002
type: task
title: Docker Compose 기동 및 MySQL 컨테이너 Health 확인
status: done
owner: devops
updated: 2025-09-22
artifacts:
  - ops: /docker-compose.yml
---
## DoD
- Compose up 시 네트워크/볼륨 생성 및 mysql 컨테이너 Healthy 상태
- 재시작 정책 및 헬스체크 동작 확인

---
id: TASK-0003
type: task
title: Arcana용 MySQL 스키마 초안 설계
status: done
owner: backend
updated: 2025-09-23
artifacts:
  - schema: /init/init.sql
  - erd: /docs/db/erd.png
---
## DoD
- users/organizations/memberships 등 핵심 테이블 초안 확정
- 기본 제약조건(UNIQUE, FK) 및 인덱스 정의

---
id: TASK-0004
type: task
title: JWT 환경변수 설정 및 검증 로직 도입
status: done
owner: backend
updated: 2025-09-26
artifacts:
  - code: /backend/utils/auth.py
---
## DoD
- JWT_SECRET_KEY/ALGORITHM/만료시간 환경변수 검증
- 잘못된 설정 시 명확한 RuntimeError 발생
- 단위테스트 통과
