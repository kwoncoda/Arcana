"""LangGraph 라우팅을 위한 행동 판단 에이전트."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Literal, Optional

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableSequence
from langchain_openai import AzureChatOpenAI
from openai import LengthFinishReasonError
from pydantic import BaseModel, Field, ValidationError

from .ai_config import _decision_load_chat_config


class _DecisionSchema(BaseModel):
    """LLM으로부터 구조화된 결정을 수집하기 위한 스키마."""

    action: Literal["search", "generate", "chat"] = Field(
        description=(
            "사용자 요청이 검색(search), 문서 생성(generate), 단순 대화(chat) 중 무엇인지 분류한 결과"
        ),
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

    action: Literal["search", "generate", "chat"]
    use_rag: bool
    rationale: str
    title_hint: Optional[str]
    instructions: Optional[str]


class DecisionAgent:
    """사용자 요청을 분석하여 다음 행동을 결정하는 에이전트."""

    def __init__(self) -> None:
        self._prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    (
                        "당신은 Arcana의 라우팅 어시스턴트입니다. "
                        "사용자의 한국어/영어 요청을 보고 search / generate / chat 중 하나의 action과 "
                        "use_rag 여부를 결정해야 합니다.\n"
                        "\n"
                        "### 액션 정의\n"
                        "1. search:\n"
                        "   - 워크스페이스 안의 기존 문서/노트/기록/파일의 위치, 내용, 존재 여부를 찾는 요청입니다.\n"
                        "   - 사용자의 과거 행동/경험/작성했던 문서를 기억에서 꺼내 달라는 질문도 포함합니다.\n"
                        "   - 예: '내가 예전에 영국 여행 갔었나?', '지난 회의록 어디 있지?', "
                        "        '전에 만들었던 API 문서 찾아줘'.\n"
                        "2. generate:\n"
                        "   - 새 문서/파일/노션 페이지/보고서/요약/초안 등을 작성하거나 재구성해 달라는 요청입니다.\n"
                        "   - 예: '지난 회의 내용으로 보고서 작성해줘', '여행 계획 문서 하나 만들어줘', "
                        "        '노션 페이지로 정리해줘', '이 내용을 문서로 깔끔하게 써줘'.\n"
                        "   - '문서', '보고서', '초안', '정리해줘', '작성해줘', '만들어줘', '노션 페이지' 같은 표현은 "
                        "     generate를 강하게 시사하는 대표적인 예시입니다.\n"
                        "   - 이런 단어가 없더라도, 사용자가 명확히 새 문서나 구조화된 결과물을 원한다면 "
                        "     generate를 선택할 수 있습니다.\n"
                        "3. chat:\n"
                        "   - 안부, 잡담, 의견, 설명 요청, 플랫폼/서비스 소개 등 "
                        "     워크스페이스 자료를 직접 찾지 않아도 되는 일반 대화입니다.\n"
                        "   - 예: '안녕', '오늘 어때?', '이 플랫폼은 어떤 플랫폼이지?', 'RAG가 뭐야?'.\n"
                        "\n"
                        "### 라우팅 규칙 (중요)\n"
                        "- 사용자가 자신의 과거 행동/기록/경험 여부를 묻는 질문(예: '~했었나?', '~갔었나?', '~있었나?')은\n"
                        "  일반적으로 search로 분류합니다. 이런 질문은 '내 기록을 확인해 줘'에 가깝습니다.\n"
                        "- 플랫폼/서비스/앱/사이트 자체를 설명해 달라는 질문은 보통 chat입니다.\n"
                        "- 단순 정보 설명, 개념 설명, 조언 요청 등은 별도로 '문서로 만들어 달라'는 요구가 없다면 chat입니다.\n"
                        "- '정리해줘', '문서로 만들어줘', '보고서 작성해줘', '노션 페이지 만들어줘'처럼 "
                        "  결과물의 형태를 명확히 지정하면 generate를 우선 고려합니다.\n"
                        "\n"
                        "### RAG 사용(use_rag)\n"
                        "- search: 기존 문서를 찾는 목적이므로 보통 use_rag=true 입니다.\n"
                        "- generate: '지난 문서/회의록/자료를 기반으로' 새 문서를 만들라는 요청이면 use_rag=true, "
                        "           아무 자료 언급 없이 완전히 새로 쓰는 경우 use_rag=false 입니다.\n"
                        "- chat: 일반 대화이므로 use_rag=false 입니다.\n"
                        "\n"
                        "### 출력 형식\n"
                        "- 항상 하나의 JSON 객체만 반환합니다.\n"
                        "- 필수 필드: action, use_rag, rationale, title_hint, instructions.\n"
                        "- action은 'search' 또는 'generate' 또는 'chat' 중 하나의 문자열입니다.\n"
                        "- rationale은 한국어로 60자 이내의 짧은 이유를 작성합니다.\n"
                        "- title_hint와 instructions는 주로 generate에서 활용 가능한 힌트가 있다면 간단히 채우고, "
                        "  없다면 null 또는 빈 문자열로 둘 수 있습니다."
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
        )
        self._tight_prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    (
                        "당신은 Arcana의 라우팅 어시스턴트입니다. "
                        "아주 짧은 JSON 한 개만 반환하세요.\n"
                        "- action: 'search' | 'generate' | 'chat'\n"
                        "- use_rag: true/false\n"
                        "- rationale: 60자 미만 한국어 설명\n"
                        "- title_hint, instructions: 필요하면 간단히 채우고, 없으면 비워두어도 됩니다.\n"
                        "\n"
                        "search: 기존 문서/기록/노트/파일을 찾거나, 사용자의 과거 행동/경험 여부를 확인하는 요청입니다.\n"
                        "generate: 새 문서/보고서/노션 페이지/요약/초안을 작성하거나 정리해 달라는 요청입니다.\n"
                        "chat: 안부, 잡담, 의견, 개념·플랫폼 설명 등 일반 대화입니다.\n"
                        "과거에 했던 일이나 갔던 곳, 만들었던 문서가 있었는지 묻는 질문은 보통 search,\n"
                        "플랫폼/서비스가 무엇인지 설명해 달라는 질문은 보통 chat,\n"
                        "무언가를 '문서로/보고서로/페이지로 만들어 달라'는 요청은 보통 generate입니다."
                    ),
                ),
                (
                    "human",
                    "사용자 요청: {query}\n추가 참고 정보: {extra_context}",
                ),
            ]
        )
        self._chain: Optional[RunnableSequence] = None
        self._llm: Optional[AzureChatOpenAI] = None

    def _ensure_llm(self) -> AzureChatOpenAI:
        if self._llm is None:
            config = _decision_load_chat_config()
            self._llm = AzureChatOpenAI(
                azure_endpoint=config["endpoint"],
                api_key=config["api_key"],
                api_version=config["api_version"],
                azure_deployment=config["deployment"],
                model=config["model"],
                temperature=0.0,
                top_p=0.0,
                max_tokens=192,
                max_retries=3,
            )
        return self._llm

    def _build_llm(self, *, max_tokens: int) -> AzureChatOpenAI:
        config = _decision_load_chat_config()
        return AzureChatOpenAI(
            azure_endpoint=config["endpoint"],
            api_key=config["api_key"],
            api_version=config["api_version"],
            azure_deployment=config["deployment"],
            model=config["model"],
            temperature=0.0,
            top_p=0.0,
            max_tokens=max_tokens,
            max_retries=2,
        )

    def _ensure_chain(self) -> RunnableSequence:
        if self._chain is None:
            llm = self._ensure_llm().with_structured_output(_DecisionSchema)
            self._chain = self._prompt | llm
        return self._chain

    @staticmethod
    def _to_agent_decision(decision: _DecisionSchema) -> AgentDecision:
        return AgentDecision(
            action=decision.action,
            use_rag=decision.use_rag,
            rationale=decision.rationale.strip() if decision.rationale else "",
            title_hint=decision.title_hint.strip() if decision.title_hint else None,
            instructions=decision.instructions.strip() if decision.instructions else None,
        )

    async def decide(self, query: str, extra_context: str = "") -> AgentDecision:
        """LLM을 호출해 행동 결정을 내린다."""

        payload = {"query": query, "extra_context": extra_context}
        chain = self._ensure_chain()

        try:
            decision: _DecisionSchema = await chain.ainvoke(payload)
            return self._to_agent_decision(decision)
        except (LengthFinishReasonError, ValidationError, json.JSONDecodeError, Exception):
            pass

        tight_llm = self._build_llm(max_tokens=128)
        tight_chain = self._tight_prompt | tight_llm.with_structured_output(_DecisionSchema)
        try:
            decision = await tight_chain.ainvoke(payload)
            return self._to_agent_decision(decision)
        except Exception:
            try:
                raw_text: str = await (self._tight_prompt | tight_llm).ainvoke(payload)
                extracted = _safe_extract_json(raw_text)
                validated = _DecisionSchema.model_validate(extracted)
                return self._to_agent_decision(validated)
            except Exception:
                fallback = _DecisionSchema(
                    action="search",
                    use_rag=True,
                    rationale="fallback-default",
                    title_hint=None,
                    instructions=None,
                )
                return self._to_agent_decision(fallback)


def _safe_extract_json(text: str) -> dict:
    """느슨한 문자열에서 JSON 객체 블록만 추출한다."""

    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not match:
        raise ValueError("No JSON object found in text")
    return json.loads(match.group(0))

