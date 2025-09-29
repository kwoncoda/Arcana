---
id: TASK-0005
type: task
title: 현재 db 로직 확인
status: done
owner: backend
updated: 2025-09-26
artifacts:
  - code: /init/init.sql
---
## DoD
- db 확인 후 현재 로직을 문서화

## Notes
- `docs/db/SCHEMA_OVERVIEW.md`에 현재 스키마 구조 요약 작성

---
id: TASK-0006
type: task
title: Notion OAuth 라우터 FastAPI 연동
status: done
owner: backend
updated: 2025-09-26
artifacts:
  - code: /backend/routers/notion.py
  - code: /backend/main.py
---
## DoD
- Notion OAuth 플로우를 FastAPI 라우터로 분리해 앱에 등록
- /login, /oauth/callback, /me/pages, /me/pages/{page_id}/content, /me/token/refresh 엔드포인트 제공
