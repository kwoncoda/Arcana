"""AI Agent 관련 스키마."""

from __future__ import annotations

from typing import Annotated, Literal, Optional

from pydantic import BaseModel, StringConstraints

from ai_module import AgentExecutionResult

QueryStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]


class SearchRequest(BaseModel):
    """워크스페이스 문서 검색 요청 페이로드."""

    query: QueryStr


class SearchResponse(BaseModel):
    """에이전트 실행 결과 응답."""

    answer: str
    mode: Literal["search", "generate"]
    notion_page_url: Optional[str] = None
    notion_page_id: Optional[str] = None

    @classmethod
    def from_execution(cls, execution: AgentExecutionResult) -> "SearchResponse":
        return cls(
            answer=execution.result.answer,
            mode=execution.mode,
            notion_page_url=execution.notion_page_url,
            notion_page_id=execution.notion_page_id,
        )
