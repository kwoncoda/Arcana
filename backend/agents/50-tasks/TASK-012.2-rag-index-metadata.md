---
id: TASK-0012.2
type: task
title: RAG 인덱스 메타데이터 동기화
status: done
owner: backend
updated: 2025-10-08
relates_to: ../40-stories/US-002.4-워크스페이스RAG스토리지메타.md
---

## 요청 사항
- `rag_indexes` 테이블에 워크스페이스별 기본 행을 만들고 `storage_uri`를 필수값으로 저장할 것.
- 회원가입 시 기본 인덱스 행을 생성·갱신하여 워크스페이스 메타데이터를 준비할 것.
- 노션 페이지 적재 완료 후 벡터/오브젝트 수와 갱신 시각을 `rag_indexes`에 반영할 것.

## 진행 내역
- `init.sql` 스키마를 최신화하여 `storage_uri NOT NULL`, `index_type='chroma'` 허용, 기본 인덱스 이름 유지.
- `users` 라우터에서 워크스페이스 생성 시 기본 인덱스 행을 upsert하도록 구현.
- `/notion/pages/pull` 플로우에서 적재된 청크/페이지 수를 기준으로 인덱스 메타데이터를 업데이트하도록 수정.

## 결과
- 워크스페이스 생성 직후 RAG 저장 경로와 메타데이터가 DB에 일관되게 보존됩니다.
- 노션 적재 진행 상황이 `object_count`, `vector_count`, `updated` 컬럼으로 추적 가능합니다.
- RAG 스토리지 경로와 메타데이터가 싱크되어 추후 상태 모니터링 및 확장 작업의 기반을 제공합니다.

## 테스트
- `python -m compileall backend`
