---
id: TASK-0008.1
type: task
title: JWT 인증 의존성 공통화 및 Swagger Authorize 연동
status: done
owner: backend
updated: 2025-10-02
artifacts:
  - code: /backend/dependencies/auth.py
  - code: /backend/dependencies/__init__.py
  - code: /backend/routers/notion.py
---

## DoD
- FastAPI `HTTPBearer` 스키마를 공용 의존성으로 정의해 Swagger Authorize 버튼과 연동
- `get_current_user` 의존성에서 `utils.auth.get_user_from_token`을 사용해 토큰 검증 및 사용자 조회
- Notion 라우터에서 공통 의존성을 주입해 헤더 파싱 로직 중복 제거

## Notes
- 향후 다른 라우터에서도 동일 의존성으로 JWT 검증을 공유 가능