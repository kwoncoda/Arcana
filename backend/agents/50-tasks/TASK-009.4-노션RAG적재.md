---
id: TASK-0009.4
type: task
title: Notion 페이지 RAG 적재 및 Chroma 연동
status: done
owner: backend
updated: 2025-10-07
---

## 요청 사항
- Notion 페이지 Pull API가 수집한 콘텐츠를 Chroma 기반 RAG 인덱스에 저장하도록 확장한다.
- LangChain 또는 LangGraph 중 서비스 구조에 적합한 기술을 채택해 임베딩/벡터 저장 파이프라인을 구축한다.
- 코드 작성 시 모든 신규 코드 라인에 주석을 추가한다.

## 진행 기록
- 2025-10-07: 기존 Notion pull 흐름 및 데이터 모델 검토, RAG 모듈 설계 초안 수립.
- 2025-10-07: Chroma 기반 RAG 서비스와 노션 페이지 → 문서 변환 유틸 구현.
- 2025-10-07: `/notion/pages/pull` API에 문서 변환 및 RAG 적재 로직 통합, 의존성 추가.

## 결과
- 노션 페이지 수집 시 LangChain Document로 변환 후 워크스페이스 단위 Chroma 컬렉션에 저장하도록 확장.
- 응답에 적재된 청크 수를 포함해 후속 처리를 위한 메타데이터 제공.

