---
id: TASK-0012.1
type: task
title: Workspace별 RAG 스토리지 파일 시스템 구성
status: done
owner: backend
updated: 2025-10-08
relates_to: ../40-stories/US-002.4-워크스페이스RAG스토리지메타.md
---

## 요청 사항
- 회원가입 시 생성/보장되는 워크스페이스마다 `/backend/storage/workspace/{workspace_name}` 디렉터리를 만들 것.
- RAG Chroma 인덱스가 워크스페이스별 디렉터리에 영속되도록 구성하고, Notion 적재 흐름에 반영할 것.
- Docker Compose에 해당 스토리지 경로가 볼륨으로 마운트되어 컨테이너 재시작 후에도 유지되도록 설정할 것.

## 진행 기록
- 2025-10-08: 기존 RAG/회원가입 코드를 검토하고 디렉터리 생성 및 경로 유틸 구조 확인.
- 2025-10-08: 워크스페이스 스토리지 유틸 및 Notion 라우터, docker-compose 수정 방안을 정리.
- 2025-10-08: Chroma 서비스가 워크스페이스 스토리지를 보장하도록 조정하고 Notion 적재 흐름 중복 코드를 제거, Compose 볼륨 정의 수정.

## 메모
- 워크스페이스 이름 기반 폴더를 만들되, 파일 시스템 안전성을 위해 슬러그 처리 필요.
- 중복 코드 제거 및 환경 변수 경로 우선순위 점검.

## 결과
- `ChromaRAGService`가 기본 스토리지 루트를 생성하고 워크스페이스별 디렉터리를 유틸과 동일한 규칙으로 보장하도록 개선.
- Notion 페이지 적재 시 중복된 JSONL 처리 블록을 제거하고 단일 경로에서 RAG 저장이 수행되도록 정리.
- `docker-compose.yml`에 워크스페이스 스토리지 볼륨을 정식으로 선언해 컨테이너 재시작 후에도 데이터가 유지되도록 구성.
