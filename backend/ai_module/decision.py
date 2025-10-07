"""LangGraph 라우팅을 위한 행동 판단 에이전트."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableSequence
from langchain_openai import AzureChatOpenAI
from pydantic import BaseModel, Field

from .rag_search import _load_chat_config


class _DecisionSchema(BaseModel):
    """LLM으로부터 구조화된 결정을 수집하기 위한 스키마."""

    action: Literal["search", "generate"] = Field(
        description="사용자 요청이 검색(search)인지 문서 생성(generate)인지 분류한 결과",
    )
    use_rag: bool = Field(
        description="생성 작업 시 기존 RAG 문서를 참고해야 하면 true",
        default=False,
    )
    rationale: str = Field(
        description="선택한 행동에 대한 간단한 근거",
        default="",
    )
    title_hint: Optional[str] = Field(
        description="생성 시 사용할 수 있는 제목 혹은 문서 주제 힌트",
        default=None,
    )
    instructions: Optional[str] = Field(
        description="생성 작업에 참고할 간단한 지침 또는 문체 정보",
        default=None,
    )


@dataclass(slots=True)
class AgentDecision:
    """라우팅 노드가 사용할 의사결정 결과."""

    action: Literal["search", "generate"]
    use_rag: bool
    rationale: str
    title_hint: Optional[str]
    instructions: Optional[str]


class DecisionAgent:
    """사용자 요청을 분석하여 다음 행동을 결정하는 에이전트."""

    def __init__(self) -> None:
        parser = JsonOutputParser(pydantic_object=_DecisionSchema)
        self._prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    (
                        "당신은 Arcana의 라우팅 어시스턴트입니다."
                        " 사용자의 요청을 읽고 다음 중 한 가지 행동을 선택하세요.\n"
                        "1. search: 사용자가 기존 문서의 위치, 존재 여부, 정보 확인을 원할 때\n"
                        "2. generate: 사용자가 새로운 문서를 작성하거나 초안을 만들어 달라고 할 때\n"
                        "생성 작업이 기존 RAG 문서 기반으로 이루어져야 한다면 use_rag를 true로 설정하세요."
                        " 예: '지난 회의록을 참고해서 보고서 작성해줘'\n"
                        "사용자가 신규 기획서/문서를 만들어 달라고만 하고 특정 문서를 참조하라고 하지 않으면"
                        " use_rag는 false입니다.\n"
                        "반드시 {format_instructions} 형식의 JSON으로만 답변하세요."
                    ),
                ),
                (
                    "human",
                    (
                        "사용자 요청: {query}\n"
                        "추가 참고 정보: {extra_context}"
                    ),
                ),
            ]
        ).partial(format_instructions=parser.get_format_instructions())
        self._parser = parser
        self._chain: Optional[RunnableSequence] = None
        self._llm: Optional[AzureChatOpenAI] = None

    def _ensure_llm(self) -> AzureChatOpenAI:
        if self._llm is None:
            config = _load_chat_config()
            self._llm = AzureChatOpenAI(
                azure_endpoint=config["endpoint"],
                api_key=config["api_key"],
                api_version=config["api_version"],
                azure_deployment=config["deployment"],
                model=config["model"],
                temperature=0.0,
                max_tokens=300,
                max_retries=3,
            )
        return self._llm

    def _ensure_chain(self) -> RunnableSequence:
        if self._chain is None:
            self._chain = self._prompt | self._ensure_llm() | self._parser
        return self._chain

    async def decide(self, query: str, extra_context: str = "") -> AgentDecision:
        """LLM을 호출해 행동 결정을 내린다."""

        chain = self._ensure_chain()
        payload = await chain.ainvoke({"query": query, "extra_context": extra_context})
        return AgentDecision(
            action=payload.action,
            use_rag=payload.use_rag,
            rationale=payload.rationale.strip(),
            title_hint=payload.title_hint.strip() if payload.title_hint else None,
            instructions=payload.instructions.strip() if payload.instructions else None,
        )

