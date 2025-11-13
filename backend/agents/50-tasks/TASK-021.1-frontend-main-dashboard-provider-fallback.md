type: task
title: 메인 대시보드 데이터 소스 렌더링 오류 수정
status: done
owner: frontend
updated: 2024-02-15
---

## 요청 사항
- 로그인 후 메인 대시보드로 리다이렉트되면 화면이 비어 있고 콘솔에 `conn.provider`가 undefined라는 오류가 발생한다.
- `/users/connections` API 응답 스키마에 맞게 프론트엔드 데이터 매핑을 수정해야 한다.

## 진행 기록
- 2024-02-15: 프론트엔드 `MainDashboard` 컴포넌트의 데이터 소스 매핑이 `conn.provider` 필드에 의존하고 있어 빈 화면이 렌더링됨을 확인했다.
- 2024-02-15: API 응답의 `type`/`name` 필드를 활용하도록 안전한 매핑 함수(`getProviderDetails`)를 추가하고 UI 렌더링 키를 업데이트했다.

## 결과
- 연결된 데이터 소스를 렌더링할 때 필수 필드가 누락되어도 안전하게 기본값을 사용하며, 메인 대시보드와 분석 사이드바가 정상적으로 동작한다.
