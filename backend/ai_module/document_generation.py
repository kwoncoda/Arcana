"""LLM을 이용해 노션 문서 초안을 생성하는 모듈."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableSequence
from langchain_openai import AzureChatOpenAI
from pydantic import BaseModel, Field

from .ai_config import _create_file_load_chat_config


class _GeneratedDocumentSchema(BaseModel):
    """생성 에이전트가 반환해야 할 문서 형태."""

    title: str = Field(description="새로 생성할 노션 페이지의 제목")
    summary: str = Field(
        description="문서의 핵심을 2~3문장 정도로 요약한 내용",
        default="",
    )
    content: str = Field(
        description="노션에 저장할 본문. 마크다운 형식 허용",
    )


@dataclass(slots=True)
class GeneratedDocument:
    """LLM이 생성한 문서 초안."""

    title: str
    summary: str
    content: str


class DocumentGenerationAgent:
    """요청과 컨텍스트를 바탕으로 마크다운 문서를 생성한다."""

    def __init__(self) -> None:
        self._prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    (
                        "당신은 Arcana의 사내 문서 작성 도우미입니다."
                        " 아래 조건을 지키며 노션 페이지 초안을 생성하세요.\n"
                        "- 제공된 컨텍스트만 활용해 한국어 마크다운 초안을 만듭니다. "
                        "- title은 간결하고 80자 이내로 작성합니다.\n"
                        "- summary는 핵심을 2~3문장으로 정리하고 400자 이내로 작성합니다.\n"
                        "- content는 한국어 마크다운 형식을 사용하며, 섹션마다 Heading을 배치합니다."
                        " 필요 시 리스트와 테이블도 마크다운으로 작성하세요.\n"
                    ),
                ),
                (
                    "human",
                    (
                        "사용자 요청: {query}\n"
                        "문서 작성 지침: {instructions}\n"
                        "참고 컨텍스트:\n"
                        "-----BEGIN CONTEXT-----\n{context}\n-----END CONTEXT-----"
                    ),
                ),
            ]
        )
        self._llm: Optional[AzureChatOpenAI] = None
        self._chain: Optional[RunnableSequence] = None

    def _ensure_llm(self) -> AzureChatOpenAI:
        if self._llm is None:
            config = _create_file_load_chat_config()
            self._llm = AzureChatOpenAI(
                azure_endpoint=config["endpoint"],
                api_key=config["api_key"],
                api_version=config["api_version"],
                azure_deployment=config["deployment"],
                model=config["model"],
                temperature=0.2,
                max_tokens=1600,
                max_retries=3,
            )
        return self._llm

    def _ensure_chain(self) -> RunnableSequence:
        if self._chain is None:
            llm_struct = self._ensure_llm().with_structured_output(_GeneratedDocumentSchema)
            self._chain = self._prompt | llm_struct
        return self._chain

    async def generate(
        self,
        *,
        query: str,
        context: str,
        instructions: Optional[str] = None,
    ) -> GeneratedDocument:
        """사용자 요청과 컨텍스트를 기반으로 문서를 생성한다."""

        chain = self._ensure_chain()
        params = {
            "query": str(query),
            "context": context or "(컨텍스트 제공되지 않음)",
            "instructions": instructions or "",
        }
        doc: _GeneratedDocumentSchema = await chain.ainvoke(params)
        return GeneratedDocument(
            title=(doc.title or "").strip(),
            summary=(doc.summary or "").strip(),
            content=(doc.content or "").strip(),
        )

