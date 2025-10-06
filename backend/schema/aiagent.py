"""AI Agent 관련 스키마."""

from __future__ import annotations

from dataclasses import asdict
from typing import Annotated, List

from pydantic import BaseModel, Field, StringConstraints

from ai_module.rag_search import Citation, SearchResult, SearchStrategy

QueryStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]


class SearchRequest(BaseModel):
    """워크스페이스 문서 검색 요청 페이로드."""

    query: QueryStr
    top_k: int = Field(default=4, ge=1, le=16, description="반환할 최대 문서 수")
    strategy: SearchStrategy = Field(
        default=SearchStrategy.VECTOR,
        description="검색 전략 (vector | keyword | hybrid)",
    )
    rerank_provider: str | None = Field(
        default=None,
        description="결과 재정렬에 사용할 프로바이더 (예: cohere)",
    )
    rerank_top_n: int | None = Field(
        default=None,
        ge=1,
        le=10,
        description="재정렬 시 고려할 상위 문서 수",
    )
    hybrid_alpha: float | None = Field(
        default=None,
        ge=0.1,
        le=1.0,
        description="하이브리드 검색 시 벡터 가중치 (0.1~1.0)",
    )


class SearchCitation(BaseModel):
    """답변에 포함되는 근거 정보를 직렬화한다."""

    page_id: str | None = None
    page_title: str | None = None
    page_url: str | None = None
    chunk_id: str | None = None
    chunk_index: int | None = None
    score: float | None = None
    snippet: str
    context_index: int | None = None


class SearchResponse(BaseModel):
    """RAG 검색 결과 응답."""

    question: str
    answer: str
    citations: List[SearchCitation]

    @classmethod
    def from_result(cls, result: SearchResult) -> "SearchResponse":
        return cls(
            question=result.question,
            answer=result.answer,
            citations=[SearchCitation(**asdict(citation)) for citation in result.citations],
        )
