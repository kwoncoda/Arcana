"""AI Agent 관련 스키마."""

from __future__ import annotations

from dataclasses import asdict
from typing import Annotated, List

from pydantic import BaseModel, StringConstraints

from ai_module.rag_search import Citation, SearchResult

QueryStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]


class SearchRequest(BaseModel):
    """워크스페이스 문서 검색 요청 페이로드."""

    query: QueryStr


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
