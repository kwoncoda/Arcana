---
id: TASK-0013.1
type: task
title: 워크스페이스 RAG 검색 API 구현
status: done
owner: backend
updated: 2025-10-09
---

## 요청 사항
- JWT 인증된 사용자가 자신의 워크스페이스 RAG 인덱스에서만 검색할 수 있는 API를 추가한다.
- LangChain/LLM 관련 로직은 `ai_module` 내부에서 구성하고, FastAPI 라우터에서는 호출만 수행한다.
- 검색 결과에는 LLM 응답과 근거 문서 메타데이터를 함께 반환한다.

## 진행 기록
- 2025-10-09: `ChromaRAGService`에 RAG 저장 경로 주입 및 `similarity_search_with_score` 기능 추가.
- 2025-10-09: 워크스페이스 공통 조회 유틸(`utils.workspace`) 생성 후 Notion 라우터에서 재사용하도록 수정.
- 2025-10-09: `WorkspaceRAGSearchAgent`를 구현하고 `/aiagent/search` 라우터와 스키마를 추가.
- 2025-10-09: FastAPI 애플리케이션에 신규 라우터를 연결하고 작업 로그 문서화.
- 2025-10-09: 벡터·BM25 하이브리드 검색에 RRF 병합과 Cohere rerank 옵션을 도입.

## 결과
- `POST /aiagent/search` 엔드포인트가 추가되어 워크스페이스 전용 RAG 검색 및 답변 생성을 수행한다.
- 검색 결과는 LLM 답변과 함께 페이지 URL, 청크 ID, 유사도 점수를 포함한 근거 정보를 반환한다.
- LLM 및 벡터DB 설정 오류 시 명확한 예외 메시지로 HTTP 상태를 매핑한다.
