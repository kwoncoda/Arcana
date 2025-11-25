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
                        "사용자의 요청을 보고 다음 중 하나의 action과 use_rag 값을 선택해야 합니다.\n"
                        "\n"
                        "### 기본 원칙 (중요)\n"
                        "- **가능한 한 대부분의 요청은 search 또는 generate로 보내세요.**\n"
                        "- **chat은 아주 짧은 인사/감정 표현/잡담일 때만 선택합니다.**\n"
                        "- 사용자가 '내용 알려줘', '~가 뭐야?', '~를 설명해줘', '~에 대해 알려줘'처럼 "
                        "정보나 개념/기술을 묻는 경우, 우선 워크스페이스 문서를 검색해야 한다고 가정하고 "
                        "반드시 search 또는 generate를 선택합니다.\n"
                        "- 애매하면 chat이 아니라 search를 선택하세요.\n"
                        "\n"
                        "### 액션 정의\n"
                        "1. search:\n"
                        "   - 워크스페이스 안의 **기존 문서/노트/기록/파일**을 찾아서 답을 준비해야 하는 요청입니다.\n"
                        "   - '내용 알려줘', '~에 대해 설명해줘', '~가 뭐야?', '~ 정리된 자료 있어?' 같이\n"
                        "     특정 주제/기술/개념/기능에 대해 묻는 대부분의 질문은 search로 분류합니다.\n"
                        "   - 사용자의 과거 행동/기록/경험 여부를 확인하는 질문도 search입니다.\n"
                        "     예: '내가 영국 여행을 갔었나?', '전에 이런 문서 만든 적 있나?'.\n"
                        "   - 예시:\n"
                        "     - '웹소켓 내용 알려줘'\n"
                        "     - '웹소켓이랑 SSE 차이 뭐야?'\n"
                        "     - '이 플랫폼은 어떤 플랫폼이지? 설명된 문서 있어?'\n"
                        "     - '우리 RAG 인덱스 구조 정리해둔 문서 찾고 싶어'\n"
                        "     → 이런 것들은 모두 **search**가 기본입니다.\n"
                        "\n"
                        "2. generate:\n"
                        "   - 새 문서/파일/노션 페이지/보고서/요약/초안을 작성하거나 재구성해 달라는 요청입니다.\n"
                        "   - 예: '지난 회의 내용을 바탕으로 보고서 작성해줘', "
                        "         '웹소켓 정리해서 노션 페이지 하나 만들어줘', "
                        "         'RAG 인덱스 구조를 문서로 정리해줘'.\n"
                        "   - '문서', '보고서', '초안', '정리해줘', '작성해줘', '만들어줘', '노션 페이지' 같은 표현은 "
                        "     generate를 강하게 시사하지만, 이런 단어가 없더라도 "
                        "     사용자가 분명히 새로운 문서/정리된 결과물을 원하면 generate를 선택할 수 있습니다.\n"
                        "\n"
                        "3. chat:\n"
                        "   - **정말 단순한 인사/잡담/감정 표현만 chat으로 보냅니다.**\n"
                        "   - 예:\n"
                        "     - '안녕', '하이', 'ㅎㅇ'\n"
                        "     - '고마워', '좋은 하루 보내', '너 진짜 똑똑하다'\n"
                        "     - '오늘 코딩하기 너무 귀찮다...'\n"
                        "   - 이런 경우에는 워크스페이스 문서를 찾을 필요가 없으므로 chat을 선택합니다.\n"
                        "   - 그 외 웬만한 질문/설명 요청은 chat이 아니라 search 또는 generate입니다.\n"
                        "\n"
                        "### RAG 사용(use_rag) 규칙\n"
                        "- search: 기존 문서/기록/노트를 찾는 것이므로 **항상 use_rag=true**로 설정합니다.\n"
                        "- generate:\n"
                        "   - '지난 문서/회의록/자료를 바탕으로' 등 기존 자료를 참고해 새 문서를 만들라는 요청이면 "
                        "     use_rag=true로 설정합니다.\n"
                        "   - 완전히 새로운 아이디어/창작물(예: 동화 지어줘, 아무 배경 없는 에세이 작성 등)은 "
                        "     use_rag=false로 둘 수 있습니다.\n"
                        "- chat: 일반 대화이므로 **use_rag=false**로 둡니다.\n"
                        "\n"
                        "### 행동 선택 요약\n"
                        "- 기술/개념/기능/플랫폼/서비스/시스템에 대해 '알려줘/설명해줘/어떤 거야?' → **우선 search**\n"
                        "- 과거에 했던 일/작성한 문서/갔던 곳 여부를 묻는 질문 → **search**\n"
                        "- 문서/보고서/페이지/요약/초안을 만들어 달라는 요청 → **generate** (필요 시 use_rag=true)\n"
                        "- 아주 짧은 인사·잡담·감정 표현만 → **chat**\n"
                        "- 헷갈릴 때는 chat이 아니라 search를 선택하세요.\n"
                        "\n"
                        "### 출력 형식\n"
                        "- 항상 하나의 JSON 객체만 반환합니다.\n"
                        "- 필수 필드: action, use_rag, rationale, title_hint, instructions.\n"
                        "- action은 반드시 'search' 또는 'generate' 또는 'chat' 중 하나입니다.\n"
                        "- rationale은 한국어로 60자 이내의 짧은 이유를 작성합니다.\n"
                        "- title_hint와 instructions는 주로 generate에서 활용 가능한 힌트가 있다면 간단히 채우고, "
                        "  없으면 null 또는 빈 문자열로 둘 수 있습니다."
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
                        "\n"
                        "- action: 'search' | 'generate' | 'chat'\n"
                        "- use_rag: true/false\n"
                        "- rationale: 60자 미만 한국어 설명\n"
                        "- title_hint, instructions: 필요하면 간단히, 없으면 비워도 됨\n"
                        "\n"
                        "**기본 원칙**\n"
                        "- 웬만한 요청은 search 또는 generate를 사용하고, chat은 정말 짧은 인사/잡담에만 사용합니다.\n"
                        "- 기술/개념/기능/플랫폼/서비스/시스템에 대해 '알려줘/설명해줘/뭐야?'라고 묻는 질문은 "
                        "대부분 search입니다.\n"
                        "- 과거에 했던 일이나 작성했던 문서/경험 여부를 묻는 질문도 search입니다.\n"
                        "- 문서/보고서/페이지/요약/초안을 만들어 달라는 요청은 generate입니다.\n"
                        "- 헷갈리면 chat이 아니라 search를 선택하세요.\n"
                        "- search일 때는 use_rag=true, chat일 때는 use_rag=false가 기본입니다."
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

