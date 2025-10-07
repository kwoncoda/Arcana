"""AI Agent 관련 스키마."""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, StringConstraints

from ai_module.rag_search import SearchResult

QueryStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]


class SearchRequest(BaseModel):
    """워크스페이스 문서 검색 요청 페이로드."""

    query: QueryStr


class SearchResponse(BaseModel):
    """RAG 검색 결과 응답."""

    answer: str

    @classmethod
    def from_result(cls, result: SearchResult) -> "SearchResponse":
        return cls(answer=result.answer)
