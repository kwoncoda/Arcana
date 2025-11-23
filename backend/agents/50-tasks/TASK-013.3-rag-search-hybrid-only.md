---
id: TASK-0013.3
type: task
title: 워크스페이스 RAG 검색 하이브리드 전략 고정 및 환경변수화
status: done
owner: backend
updated: 2025-10-10
---

## 요청 사항
- `/aiagent/search` API가 항상 하이브리드 검색을 사용하도록 수정합니다.
- 검색 파라미터 `top_k`, `hybrid_alpha`를 프론트 입력 대신 `.env` 환경 변수(`TOP_K`, `HYBRID_ALPHA`)로 제어합니다.
- 불필요한 검색 전략 분기와 관련 스키마 필드를 제거합니다.
- `ChromaRAGService.hybrid_search_with_score`의 후보 계산 구간에 대한 한국어 주석을 추가합니다.

## 진행 기록
- 2025-10-10: 요구사항 파악 및 관련 코드 베이스 분석.
- 2025-10-10: `/aiagent/search` 요청 스키마와 라우터에서 전략·파라미터 입력을 제거하고 에이전트가 환경 변수 기반 하이브리드 검색만 수행하도록 정리.
- 2025-10-10: `ChromaRAGService.hybrid_search_with_score`에 주석을 추가하고 불필요한 검색 헬퍼를 제거하여 내부에서 직접 벡터·BM25 검색을 조합하도록 수정.

## 결과
- 백엔드가 `.env`의 `TOP_K`, `HYBRID_ALPHA` 값으로만 검색 파라미터를 제어하며, API는 질문 문자열만 받는다.
- 하이브리드 검색 경로 외 코드가 정리되어 유지보수 범위가 축소되고, 후보 계산 로직에는 한국어 주석이 추가되었다.

