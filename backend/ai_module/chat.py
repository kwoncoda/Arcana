"""단순 대화 요청을 처리하는 에이전트."""
from __future__ import annotations

import logging
from typing import Optional

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableSequence
from langchain_openai import AzureChatOpenAI

from .ai_config import _gpt5_load_chat_config

logger = logging.getLogger("arcana")


class ChatAgent:
    """워크스페이스 문맥이 필요 없는 일반 대화를 처리한다."""

    def __init__(self) -> None:
        self._prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    (
                        "당신은 Arcana의 대화형 어시스턴트입니다."
                        " 사용자의 메시지에 친근하고 간결하게 2~4문장으로 답하세요.\n"
                        "워크스페이스 문서나 외부 링크는 언급하지 말고, 필요한 경우 추가 자료가 없다고 솔직히 말합니다."
                        "이 서비스는 연동된 모든 외부 데이터 소스를 검색 후 생성할 수 있는 플랫폼입니다."
                    ),
                ),
                (
                    "human",
                    "사용자 메시지: {query}\n자연스러운 한국어로 답변하세요.",
                ),
            ]
        )
        self._parser = StrOutputParser()
        self._llm: Optional[AzureChatOpenAI] = None
        self._chain: Optional[RunnableSequence] = None

    def _ensure_llm(self) -> AzureChatOpenAI:
        if self._llm is None:
            config = _gpt5_load_chat_config()
            self._llm = AzureChatOpenAI(
                azure_endpoint=config["endpoint"],
                api_key=config["api_key"],
                api_version=config["api_version"],
                azure_deployment=config["deployment"],
                model=config["model"],
                temperature=0.4,
                max_tokens=400,
                max_retries=3,
            )
        return self._llm

    def _ensure_chain(self) -> RunnableSequence:
        if self._chain is None:
            llm = self._ensure_llm()
            self._chain = self._prompt | llm | self._parser
        return self._chain

    async def respond(self, query: str) -> str:
        """대화 응답을 생성한다."""

        chain = self._ensure_chain()
        try:
            answer = await chain.ainvoke({"query": query})
        except Exception as exc:  # pragma: no cover - 외부 API 방어
            logger.exception("ChatAgent 응답 생성 실패: %s", exc)
            return "지금은 답변을 준비하지 못했어요. 다시 한번 말씀해 주세요."

        cleaned = (answer or "").strip()
        if not cleaned:
            return "지금은 답변을 준비하지 못했어요. 다시 한번 말씀해 주세요."
        return cleaned
