---
id: TASK-0009.2
category: backend
status: done
title: "Notion OAuth 토큰 리프레시 유틸 구현"
updated: 2025-02-14
artifacts:
  - code: backend/notions/notion.py
  - code: backend/notions/__init__.py
relates_to: ["US-002.2"]
---

## 배경
- Notion OAuth 연동 이후 access_token이 만료되면 API 호출이 401 오류로 실패하고, 재로그인을 강제해야 했다.
- 기존 구현에는 refresh_token을 활용한 재발급 경로가 없어 `NotionOauthCredentials`의 만료 시각(`expires`)이 무의미했다.

## 작업 범위
1. 토큰 만료 여부를 사전에 감지할 수 있는 헬퍼를 작성한다.
2. refresh_token으로 access_token을 재발급하고 ORM 엔티티를 갱신하는 로직을 추가한다.
3. 외부 모듈에서 재사용할 수 있도록 헬퍼들을 패키지 루트에서 export한다.

## 구현 메모
- `_REFRESH_SAFETY_WINDOW`를 90초로 두어 Notion API 호출 직전에 토큰이 만료되는 레이스 컨디션을 방지했다.
- `should_refresh_token`은 access_token 누락 혹은 만료 예정 시점을 확인해 선제적으로 재발급 여부를 판단한다.
- `refresh_access_token`은 Notion OAuth 토큰 엔드포인트에 `grant_type=refresh_token`으로 POST를 보내고, 응답을 `apply_oauth_tokens`와 공유해 DB 커밋 로직을 재사용한다.
- `ensure_valid_access_token`은 호출부에서 간단하게 사용할 수 있는 파사드로, 토큰 만료 여부를 확인한 뒤 필요한 경우 한 번만 재발급을 수행한다.

## 산출물
- `backend/notions/notion.py`
  - 만료 감지, 재발급, 워크스페이스별 자격 증명 조회 유틸이 추가됐다.
- `backend/notions/__init__.py`
  - 신규 헬퍼들을 export해 라우터나 서비스 모듈이 직접 import할 수 있다.

## 후속 과제
- Notion API 연동부에서 `ensure_valid_access_token`을 호출해 자동 갱신을 실제 워크플로우에 통합한다.
- 장기적으로 refresh_token도 만료될 수 있으므로, 재연동을 안내하는 사용자 메시지 전략이 필요하다.