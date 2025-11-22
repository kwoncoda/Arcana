"""최종 사용자 답변을 다듬는 에이전트."""
from __future__ import annotations

from typing import Literal, Optional

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableSequence
from langchain_openai import AzureChatOpenAI

from .ai_config import _final_answer_load_chat_config


class FinalAnswerAgent:
    """검색/생성 결과 초안을 사용자-facing 문장으로 정리한다."""

    def __init__(self) -> None:
        self._prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    (
                        "당신은 Arcana의 응답 편집기입니다."
                        " 제공된 초안(answer_draft)만 활용해 사용자에게 전달할 최종 문장을 한국어로 다듬으세요.\n"
                        "- 새로운 사실이나 URL을 만들지 말고, 초안에 있는 정보만 유지하세요.\n"
                        "- 초안에 포함된 URL/인용 라인은 그대로 보존하세요.\n"
                        "- 필요하면 문장을 더 읽기 쉽게 정리하되, 의미를 왜곡하지 마세요.\n"
                        "- chat 모드에서는 워크스페이스 문서를 언급하지 말고 자연스럽게 대화하세요.\n"
                        "- generate 모드에서는 생성된 문서의 제목/요약/URL이 있으면 그대로 알려주세요.\n"
                    ),
                ),
                (
                    "human",
                    (
                        "모드: {mode}\n"
                        "워크스페이스: {workspace_name}\n"
                        "사용자 질문: {question}\n"
                        "추가 가이드: {custom_instructions}\n"
                        "초안(answer_draft):\n{answer_draft}\n\n"
                        "위 초안을 사용자에게 보여줄 최종 문장으로 정제하세요."
                    ),
                ),
            ]
        )
        self._parser = StrOutputParser()
        self._llm: Optional[AzureChatOpenAI] = None
        self._chain: Optional[RunnableSequence] = None

    def _ensure_llm(self) -> AzureChatOpenAI:
        if self._llm is None:
            config = _final_answer_load_chat_config()
            self._llm = AzureChatOpenAI(
                azure_endpoint=config["endpoint"],
                api_key=config["api_key"],
                api_version=config["api_version"],
                azure_deployment=config["deployment"],
                model=config["model"],
                temperature=0.2,
                max_tokens=600,
                max_retries=3,
            )
        return self._llm

    def _ensure_chain(self) -> RunnableSequence:
        if self._chain is None:
            llm = self._ensure_llm()
            self._chain = self._prompt | llm | self._parser
        return self._chain

    async def craft_final_answer(
        self,
        *,
        answer_draft: str,
        question: str,
        workspace_name: str,
        mode: Literal["search", "generate", "chat"],
        custom_instructions: Optional[str] = None,
    ) -> str:
        """최종 사용자 응답을 생성한다."""

        chain = self._ensure_chain()
        payload = {
            "answer_draft": answer_draft,
            "question": question,
            "workspace_name": workspace_name,
            "mode": mode,
            "custom_instructions": custom_instructions or "(추가 가이드 없음)",
        }

        try:
            rendered = await chain.ainvoke(payload)
        except Exception:
            # 편집 실패 시 초안을 그대로 사용해 빈 응답을 방지한다.
            return answer_draft.strip() or "지금은 답변을 준비하지 못했어요. 다시 한번 말씀해 주세요."

        refined = rendered.strip()
        if refined:
            return refined
        # 모델이 빈 문자열을 반환한 경우 초안을 그대로 전달한다.
        return answer_draft.strip() or "지금은 답변을 준비하지 못했어요. 다시 한번 말씀해 주세요."

