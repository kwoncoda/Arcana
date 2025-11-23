---
id: TASK-024.1
type: task
title: 채팅 전송/정지 토글 및 즉시 중단 처리
status: done
owner: frontend
updated: 2025-02-17
artifacts:
  - code: /frontend/my-react-app/src/components/MainDashboard.jsx
---

## 요청 사항
- 전송 버튼을 눌러 Arcana AI 응답이 생성될 때 버튼 텍스트를 "정지"로 변경하고, 클릭 시 즉시 응답 생성을 중단하도록 개선해 달라는 요청.

## 작업 내용
- 채팅 요청에 `AbortController`를 연결해 생성 중인 Axios 호출을 안전하게 취소할 수 있게 추가.
- 전송 버튼을 로딩 상태에서는 "정지" 라벨과 정지 아이콘이 나타나도록 스타일과 동작을 토글.
- 정지 버튼 클릭 시 진행 중인 요청을 즉시 중단하고 로딩 상태를 해제하도록 처리.

## 결과
- 전송 중에 버튼이 정지 상태로 전환되며, 사용자가 정지 버튼을 누르면 즉시 API 요청이 취소되어 추가 응답 생성 없이 종료됨을 확인.
