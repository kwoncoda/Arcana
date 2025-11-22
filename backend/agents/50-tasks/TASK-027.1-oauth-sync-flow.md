---
id: TASK-027.1
type: task
title: OAuth 연동 후 대시보드 우선 진입 및 동기화 UX 개선
status: done
owner: frontend
updated: 2025-02-27
artifacts:
  - code: /frontend/my-react-app/src/components/NotionOAuthCallback.jsx
  - code: /frontend/my-react-app/src/components/GoogleOAuthCallback.jsx
  - code: /frontend/my-react-app/src/components/MainDashboard.jsx
---

## 요청 사항
- OAuth 연동 완료 시 RAG 적재를 기다리지 말고 즉시 메인 대시보드로 이동하도록 UX를 변경해달라는 요청.
- 대시보드에서 지식 베이스 갱신 버튼 클릭 시 전체 화면 로딩 오버레이를 띄워 다른 동작을 막아달라는 요구.
- 연동 직후 데이터 소스 갱신도 동일한 방식의 로딩 오버레이를 사용해 진행하도록 정렬.

## 작업 계획
- 각 OAuth 콜백 컴포넌트에서 RAG 적재 요청을 제거하고, 대시보드로 이동하면서 동기화 트리거 정보를 전달하도록 변경.
- 메인 대시보드에서 전달된 트리거에 따라 자동 동기화를 수행하되, 진행 동안 전체 화면 오버레이를 표시하도록 UI를 개선.
- 수동 지식 베이스 갱신 버튼 동작도 동일한 오버레이를 사용하도록 통합.

## 작업 내용
- Notion/Google OAuth 콜백에서 RAG 적재 호출을 제거하고, 대시보드로 이동하면서 동기화 트리거 정보를 상태로 전달하도록 변경.
- 메인 대시보드에 전면 로딩 오버레이를 추가해 지식 베이스 갱신 및 자동 동기화 시 사용자 입력을 차단하도록 구현.
- 자동/수동 동기화 모두 동일한 함수로 처리하도록 통합하고, 연동된 소스만 선택적으로 갱신할 수 있도록 필터링 로직을 추가.

## 결과
- OAuth 연동 직후 사용자가 대시보드로 즉시 이동하며, 이후 데이터 소스 갱신이 오버레이와 함께 진행되어 중간 입력이 차단됨.
- 지식 베이스 갱신 버튼과 자동 갱신 모두 동일한 UX로 진행 상황이 안내되어 일관성이 확보됨.
