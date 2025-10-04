---
id: TASK-0009.1
type: task
title: Notion OAuth 연동 백엔드 구현
status: done
owner: backend
updated: 2025-10-05
artifacts:
  - code: /backend/routers/notion.py
  - code: /backend/notions/notion.py
  - code: /backend/models/entities.py
  - code: /backend/pyproject.toml
relates_to: ["US-002.1"]
---

## DoD
- FastAPI `/notion/connect` 및 `/notion/oauth/callback` 라우터로 Notion OAuth 플로우(Authorize URL 발급, 콜백 처리)를 완성했다.
- 데이터 소스/자격증명을 자동 생성하는 `_ensure_notion_resources` 로직과 토큰 저장 유틸 `apply_oauth_tokens` 로 상태 전환(`disconnected`→`connected`)이 가능하다.
- 환경변수 `NOTION_CLIENT_ID/SECRET/REDIRECT_URI` 기반 OAuth 설정과 `notion-client` 의존성을 프로젝트에 추가했다.
- `NotionOauthCredentials`, `DataSource` ORM 모델로 사용자-워크스페이스별 토큰/상태를 영속화한다.

## Notes
- 현재 OAuth state는 인메모리 캐시로 관리되므로 운영 배포 시 Redis 등 외부 스토리지로 교체 필요.