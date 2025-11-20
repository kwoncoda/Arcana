"""LangGraph를 이용한 검색/생성 라우팅 오케스트레이터."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional, TypedDict

from langgraph.graph import END, StateGraph
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from models import Workspace

from notions.notionAuth import (
    get_connected_user_credential,
    NotionCredentialError,
)
from notions.notionCreate import NotionPageReference, create_page_from_markdown

from .decision import AgentDecision, DecisionAgent
from .document_generation import DocumentGenerationAgent, GeneratedDocument
from .final_answer import FinalAnswerAgent
from .rag_search import (
    RetrievalPayload,
    SearchResult,
    WorkspaceRAGSearchAgent,
)


class AgentState(TypedDict, total=False):
    """LangGraph 실행 중 공유되는 상태."""

    query: str
    workspace_idx: int
    workspace_name: str
    storage_uri: Optional[str]
    db: Session
    user_idx: int
    decision: AgentDecision
    retrieval: RetrievalPayload
    generated_document: GeneratedDocument
    result: SearchResult
    mode: Literal["search", "generate"]
    notion_page: NotionPageReference
    final_message_instructions: Optional[str]


@dataclass(slots=True)
class AgentExecutionResult:
    """그래프 실행이 끝난 뒤 API 계층에 전달할 결과."""

    mode: Literal["search", "generate"]
    result: SearchResult
    notion_page_id: Optional[str] = None
    notion_page_url: Optional[str] = None
    decision: Optional[AgentDecision] = None
    generated_document: Optional[GeneratedDocument] = None


class WorkspaceAgentOrchestrator:
    """LangGraph를 통해 검색과 문서 생성을 분기 처리하는 오케스트레이터."""

    def __init__(
        self,
        *,
        search_agent: Optional[WorkspaceRAGSearchAgent] = None,
        decision_agent: Optional[DecisionAgent] = None,
        generation_agent: Optional[DocumentGenerationAgent] = None,
        final_answer_agent: Optional[FinalAnswerAgent] = None,
    ) -> None:
        self._search_agent = search_agent or WorkspaceRAGSearchAgent()
        self._decision_agent = decision_agent or DecisionAgent()
        self._generation_agent = generation_agent or DocumentGenerationAgent()
        self._final_answer_agent = final_answer_agent or FinalAnswerAgent()
        self._graph = self._build_graph()

    def _build_graph(self):
        graph = StateGraph(AgentState)
        graph.add_node("decide", self._node_decide)
        graph.add_node("search", self._node_search)
        graph.add_node("prepare_rag", self._node_prepare_rag)
        graph.add_node("generate", self._node_generate)
        graph.add_node("create_page", self._node_create_page)
        graph.add_node("final_answer", self._node_finalize)

        graph.set_entry_point("decide")
        graph.add_conditional_edges(
            "decide",
            self._route_from_decision,
            {
                "search": "search",
                "generate_with_rag": "prepare_rag",
                "generate_without_rag": "generate",
                "end": END,
            },
        )
        graph.add_edge("prepare_rag", "generate")
        graph.add_edge("generate", "create_page")
        graph.add_edge("search", "final_answer")
        graph.add_edge("create_page", "final_answer")
        graph.add_edge("final_answer", END)

        return graph.compile()

    async def _node_decide(self, state: AgentState) -> AgentState:
        decision = await self._decision_agent.decide(query=state["query"])
        return {"decision": decision}

    async def _node_search(self, state: AgentState) -> AgentState:
        result = await run_in_threadpool(
            self._search_agent.search,
            workspace_idx=state["workspace_idx"],
            workspace_name=state["workspace_name"],
            query=state["query"],
            storage_uri=state.get("storage_uri"),
        )
        return {"result": result, "mode": "search"}

    async def _node_prepare_rag(self, state: AgentState) -> AgentState:
        payload = await run_in_threadpool(
            self._search_agent.retrieve_for_generation,
            workspace_idx=state["workspace_idx"],
            workspace_name=state["workspace_name"],
            query=state["query"],
            storage_uri=state.get("storage_uri"),
        )
        return {"retrieval": payload}

    async def _node_generate(self, state: AgentState) -> AgentState:
        retrieval = state.get("retrieval")
        context = retrieval.context if retrieval else ""
        decision = state["decision"]
        generated = await self._generation_agent.generate(
            query=state["query"],
            context=context,
            instructions=decision.instructions,
        )
        return {"generated_document": generated, "mode": "generate"}

    async def _node_create_page(self, state: AgentState) -> AgentState:
        generated = state.get("generated_document")
        if not generated:
            raise RuntimeError("생성된 문서가 없어 노션 페이지를 만들 수 없습니다.")

        retrieval = state.get("retrieval")
        citations = retrieval.citations if retrieval else []

        try:
            credential = get_connected_user_credential(
                state["db"],
                workspace_idx=state["workspace_idx"],
                user_idx=state["user_idx"],
            )
        except NotionCredentialError as exc:
            raise NotionCredentialError(str(exc)) from exc

        page_ref = await create_page_from_markdown(
            state["db"],
            credential,
            title=generated.title,
            markdown=generated.content,
        )

        lines = [
            "요청하신 내용을 바탕으로 노션 페이지를 생성했습니다.",
            f"제목: {generated.title or '제목 없음'}",
        ]
        if generated.summary:
            lines.append(f"요약: {generated.summary}")
        if page_ref.url:
            lines.append(page_ref.url)
        else:
            lines.append("노션 페이지 URL을 가져오지 못했습니다.")
        answer = "\n".join(lines)

        result = SearchResult(
            question=state["query"],
            answer=answer,
            citations=list(citations),
        )
        return {"result": result, "notion_page": page_ref}

    async def _node_finalize(self, state: AgentState) -> AgentState:
        """사용자에게 전달할 최종 답변을 정리한다."""

        result = state.get("result")
        if not result:
            raise RuntimeError("최종 답변이 준비되지 않았습니다.")

        mode = state.get("mode", "search")
        instructions = state.get("final_message_instructions")
        refined_answer = await self._final_answer_agent.craft_final_answer(
            answer_draft=result.answer,
            question=result.question,
            workspace_name=state.get("workspace_name", ""),
            mode=mode,
            custom_instructions=instructions,
        )
        refined_result = SearchResult(
            question=result.question,
            answer=refined_answer,
            citations=result.citations,
        )
        return {"result": refined_result, "mode": mode}

    @staticmethod
    def _route_from_decision(state: AgentState) -> str:
        decision = state.get("decision")
        if not decision:
            return "end"
        if decision.action == "search":
            return "search"
        if decision.action == "generate":
            return "generate_with_rag" if decision.use_rag else "generate_without_rag"
        return "search"

    async def run(
        self,
        *,
        db: Session,
        user_idx: int,
        workspace: Workspace,
        storage_uri: Optional[str],
        query: str,
        final_message_instructions: Optional[str] = None,
    ) -> AgentExecutionResult:
        """그래프를 실행하고 결과를 반환한다."""

        initial_state: AgentState = {
            "query": query,
            "workspace_idx": workspace.idx,
            "workspace_name": workspace.name,
            "storage_uri": storage_uri,
            "db": db,
            "user_idx": user_idx,
            "final_message_instructions": final_message_instructions,
        }

        final_state = await self._graph.ainvoke(initial_state)
        result = final_state.get("result")
        if not result:
            raise RuntimeError("에이전트가 결과를 생성하지 못했습니다.")

        mode = final_state.get("mode", "search")
        page_ref = final_state.get("notion_page")
        return AgentExecutionResult(
            mode=mode,
            result=result,
            notion_page_id=page_ref.page_id if page_ref else None,
            notion_page_url=page_ref.url if page_ref else None,
            decision=final_state.get("decision"),
            generated_document=final_state.get("generated_document"),
        )

