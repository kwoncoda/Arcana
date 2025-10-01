---
id: TASK-0007
type: task
title: Notion OAuth 라우터 FastAPI 연동
status: done
owner: backend
updated: 2025-09-29
artifacts:
  - code: /backend/routers/notion.py
  - code: /backend/main.py
---
## DoD
- Notion OAuth 플로우를 FastAPI 라우터로 분리해 앱에 등록
- /login, /oauth/callback, /me/pages, /me/pages/{page_id}/content, /me/token/refresh 엔드포인트 제공