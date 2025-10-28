---
id: TASK-0015.2
type: task
title: 노션 RAG 페이지 청킹 및 메타데이터 정리
status: done
owner: backend
updated: 2025-10-27
---

## 요청 사항
- 노션 페이지를 JSONL로 변환할 때 페이지 단위로 우선 직렬화하고, 토큰 한도를 초과할 때만 문단 경계 기준으로 청킹합니다.
- `block_metadata` 대신 `block_types`와 구조 구분자를 활용하여 크로마 호환 메타데이터를 구성합니다.
- 렌더링된 마크다운 텍스트 안에 블록 타입을 식별할 수 있는 토큰(`[[H2]]`, `[[P]]` 등)을 삽입해 후처리 및 하이라이팅을 용이하게 합니다.

## 진행 기록
- 2025-10-27: 기존 ragTransform 청킹 로직을 분석하고 페이지 수준 텍스트 유지 전략을 수립했습니다.
- 2025-10-27: Notion 렌더러를 정리하고 리스트 들여쓰기, 블록 간 공백을 재검토했습니다.
- 2025-10-27: JSONL 레코드 스키마를 수정하여 `block_metadata`를 제거하고 `block_types`, `block_markers`, `block_depths`, `block_starts` 배열을 추가했습니다.
- 2025-10-27: LangChain Document 생성 시 메타데이터를 JSON 직렬화된 문자열로 저장해 크로마 제약(str|int|float|bool)을 준수하도록 변경했습니다.
- 2025-10-27: GPT 피드백의 `_update_fence_state` 중복 정의 지적은 현재 코드베이스에 존재하지 않음을 확인했습니다.

## 결과
- 페이지 전체 텍스트를 하나의 청크로 유지하되, 토큰 제한을 넘는 경우에만 annotated segment 단위로 분할합니다.
- 마크다운 텍스트에 희소 구분 토큰을 삽입하여 RAG 검색 후 블록 경계를 쉽게 복원할 수 있습니다.
- `block_types`, `block_markers`, `block_depths`, `block_starts`를 JSONL과 Document 메타데이터에 포함해 구조 정보를 경량으로 유지합니다.
- 크로마 호환성을 유지하기 위해 모든 배열형 메타데이터를 JSON 문자열로 변환했습니다.