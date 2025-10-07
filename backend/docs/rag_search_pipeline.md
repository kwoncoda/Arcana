# 워크스페이스 RAG 검색·답변 파이프라인 정리

## 1. 개요
본 문서는 2025-10-09 이후 개편된 워크스페이스 RAG 검색과 답변 생성 흐름을 설명한다. Cohere 기반 재정렬 단계를 제거하고 LangChain 런너블 체인을 활용해 검색과 답변 생성을 일관된 파이프라인으로 구성했다.

## 2. 검색 전략 구성
- **SearchStrategy** 열거형은 `vector`, `keyword`, `hybrid` 세 가지 전략을 지원한다.
- `ChromaRAGService`는 워크스페이스별 벡터 스토어와 BM25 인덱스를 관리한다.
  - `similarity_search_with_score`: 순수 벡터 검색.
  - `keyword_search_with_score`: BM25 기반 키워드 검색.
  - `hybrid_search_with_score`: 가중치(`alpha`)와 RRF 결합(`rrf_k`)을 이용한 하이브리드 검색.
- LangChain `Document` 객체와 점수 쌍을 반환하도록 정규화하여 이후 단계가 입력 형식에 의존하지 않도록 했다.

## 3. 컨텍스트 구축
- `_build_context`는 각 문서를 순회하며 `[번호] 제목/URL/본문` 형태의 블록을 만든다.
- `context_index` 계산을 위해 `chunk_id`, `page_id`, `rag_document_id`를 맵에 기록한다.
- 컨텍스트가 12,000자 이상이면 문서 수를 줄여 프롬프트 길이를 제한한다.

## 4. LangChain 기반 답변 체인
- `_ensure_response_chain`은 LangChain `RunnableMap`과 `RunnableLambda`로 질문·컨텍스트를 프롬프트에 주입하는 시퀀스를 구성한다.
- 프롬프트 → `AzureChatOpenAI` → `StrOutputParser` 순으로 연결된 `RunnableSequence`를 재사용한다.
- 체인은 `invoke({"question": ..., "context": ...})` 호출만으로 답변을 생성하며, LangChain이 재시도와 스트리밍 옵션을 관리할 수 있다.

## 5. 출처 정리
- `_build_citations`는 중복 청크를 제거하고 요약 스니펫, 점수, `context_index`를 포함하는 `Citation` 객체 목록을 생성한다.
- 이 정보는 `SearchResponse` 직렬화 시 그대로 활용되어 UI에서 근거 표기가 가능하다.

## 6. 파라미터 기본값
- `top_k`는 최소 1, 최대 10으로 제한한다.
- 하이브리드 검색은 `hybrid_alpha`(0 < α ≤ 1)와 `hybrid_rrf_k`(기본 60)를 사용한다.
- Cohere Rerank 옵션이 제거되면서 후보 수 산정은 `top_k` 기반으로 간소화되었다.

## 7. 예외 처리
- 질문이 비어 있으면 `ValueError`로 클라이언트에 400 응답을 보낸다.
- Azure OpenAI 설정이 누락되면 명시적인 `RuntimeError`를 발생시켜 500 응답으로 매핑한다.
- LLM 호출 실패 시 경고 로그와 함께 사용자에게 재시도를 안내하는 메시지를 반환한다.

## 8. 후속 작업 아이디어
- LangChain `Runnable`을 이용해 검색 결과 로그를 비동기 저장하는 후처리 단계를 추가할 수 있다.
- 사용자 피드백을 반영해 `hybrid_alpha`를 자동 조정하거나, 필요 시 추가적인 재정렬 모델을 도입할 수 있도록 확장성을 확보했다.
