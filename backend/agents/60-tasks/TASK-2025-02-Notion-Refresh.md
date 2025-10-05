---
id: TASK-2025-02-NOTION-REFRESH
status: done
owner: backend
updated: 2025-02-14
---

## Request
- 사용자 피드백: Notion OAuth 연동 후 리프레시 토큰을 이용한 access_token 재발급 로직이 없음.

## Approach
- 기존 `backend/notions/notion.py` 유틸을 확장해 토큰 만료 판단 및 재발급 헬퍼를 추가한다.
- 필요 시에만 Notion API `grant_type=refresh_token` 호출하도록 구현한다.

## Result
- `should_refresh_token`, `refresh_access_token`, `ensure_valid_access_token` 등 유틸을 추가해 토큰 만료시 자동 재발급이 가능하다.
- 워크스페이스 ID로 자격증명을 조회하는 헬퍼와 토큰 응답 머지 로직을 보강했다.
