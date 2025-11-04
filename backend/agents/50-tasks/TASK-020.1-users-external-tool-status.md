type: task
title: 사용자 외부 도구 연동 현황 API 추가
status: done
owner: backend
updated: 2025-02-15
---

## 요청 사항
- 프론트엔드에서 로그인한 사용자가 어떤 외부 도구를 연동했는지 확인할 수 있는 API가 필요하다.
- 노션 연동과 같이 데이터 소스에 연결 여부를 Boolean 형태로 반환해야 한다.

## 진행 기록
- 2025-02-15: 외부 도구 응답을 표현할 Pydantic 스키마(`ExternalToolStatus`, `ExternalToolConnectionsResponse`)를 추가했다.
- 2025-02-15: 사용자 기본 워크스페이스의 데이터 소스를 조회해 상태를 정리하는 `/users/connections` 엔드포인트를 구현했다.
- 2025-02-15: 신규 작업 내역을 문서화했다.

## 결과
- `GET /users/connections` 호출 시 워크스페이스에 등록된 모든 데이터 소스의 타입, 이름, 상태, 동기화 시각을 반환한다.
- 프론트엔드는 `connected` 필드로 외부 도구 연동 여부를 직관적으로 판단할 수 있다.
