---
id: TASK-FE-TOKEN-REFRESH-CLIENT
category: frontend
status: in_progress
title: "프런트엔드 공통 클라이언트 토큰 재발급 적용 기록"
updated: 2025-02-11
artifacts:
  - code: frontend/my-react-app/src/api/client.js
  - code: frontend/my-react-app/src/api/authStorage.js
  - code: frontend/my-react-app/src/components/MainDashboard.jsx
  - code: frontend/my-react-app/src/components/LoginPage.jsx
  - code: frontend/my-react-app/src/components/GoogleOAuthCallback.jsx
  - code: frontend/my-react-app/src/components/NotionOAuthCallback.jsx
  - code: frontend/my-react-app/src/components/NotionConnectPage.jsx
  - code: frontend/my-react-app/src/components/RegisterPage.jsx
  - code: frontend/my-react-app/src/components/MyPage.jsx
relates_to: ["US-001.3"]
---

## 작업 개요
- 액세스 토큰 만료 시 `/api/users/token/refresh`로 새 토큰을 받아 실패했던 요청을 한 번 재시도하는 공통 axios 클라이언트를 도입했다.
- 토큰 저장소를 `sessionStorage` 우선으로 구성하고, 기존 `localStorage` 값이 있을 경우 읽어서 이동한 뒤 로그아웃 시 두 저장소를 모두 정리하도록 통합 헬퍼를 추가했다.
- 대시보드, OAuth 콜백, 로그인/회원가입, 로그아웃 등 주요 진입점이 공통 클라이언트와 저장소 헬퍼를 사용하도록 교체했다.

## 구현 요약
- `frontend/my-react-app/src/api/client.js`: 요청 인터셉터에서 액세스 토큰을 자동으로 주입하고, 응답 인터셉터에서 401을 감지하면 리프레시 토큰으로 재발급 후 원 요청을 최대 한 번 재전송한다. 재발급 실패 시 저장소를 정리하고 `/login`으로 이동한다.
- `frontend/my-react-app/src/api/authStorage.js`: `sessionStorage` 기반으로 `get/set/clear` API를 제공하며, 최초 접근 시 `localStorage`에 남아 있는 토큰을 회수해 세션 저장소로 옮긴다. 두 저장소 모두 비워 주는 `clearAll`을 노출한다.
- 주요 페이지/컴포넌트는 이전에 직접 axios를 사용하던 부분을 공통 클라이언트로 교체했고, 로그인·회원가입 성공 시 새 토큰 저장 헬퍼를, 로그아웃 시 `clearAll()`을 호출하도록 통일했다.

## 남은 확인 사항
- 네트워크 재시도 횟수(현재 1회)와 재시도 지연(backoff) 적용 여부 결정 필요.
- 토큰 재발급 API 경로가 백엔드 배포 환경에 따라 다를 수 있으므로 베이스 URL 구성 검토 필요.
- 동시 탭 간 토큰 재발급 경쟁 및 브로드캐스트 채널 동기화 여부는 미구현 상태.
