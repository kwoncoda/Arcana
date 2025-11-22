---
id: TASK-0023.1
type: task
title: 데이터 소스 연동 해제 API 구현
status: done
owner: backend
updated: 2025-11-20
---

## 요청 사항
- Notion과 Google Drive 연동을 끊는 API를 각각의 라우터에 추가한다.
- 연동 해제 시 RAG 인덱스에서 해당 데이터 소스의 문서를 제거하고 메타데이터를 갱신한다.
- Google Drive의 Changes API 상태 및 파일 스냅샷을 포함한 부수 데이터를 함께 정리한다.

## 진행 기록
- 2025-11-20: 요구사항 확인 및 관련 라우터, RAG 서비스 구조 파악.
- 2025-11-20: Notion/Google Drive 연동 해제 API를 구현하고 RAG 서비스에 메타데이터 삭제 헬퍼를 추가.
- 2025-11-20: Google Drive Changes API 상태 및 스냅샷, 저장소 파일을 제거하도록 처리.

## 결과
- Notion/Google Drive 라우터에 연동 해제 엔드포인트가 추가되어 데이터 소스 상태와 자격증명, RAG 인덱스를 정리한다.
- Google Drive 연동 해제 시 Changes API 상태, 파일 스냅샷, 워크스페이스 저장 파일이 함께 삭제된다.
