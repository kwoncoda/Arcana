"""Chroma 기반 RAG 적재 및 검색 서비스."""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from threading import RLock
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
from uuid import uuid4

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_openai import AzureOpenAIEmbeddings
from rank_bm25 import BM25Okapi

from utils.workspace_storage import ensure_workspace_storage, workspace_storage_path

from ai_module.ai_config import _EM_load_azure_openai_config

_DEFAULT_STORAGE_ROOT = workspace_storage_path("_").parent
_TOKEN_PATTERN = re.compile(r"[\w가-힣]+", re.UNICODE)


@dataclass(slots=True)
class _KeywordIndex:
    """키워드 검색을 위한 메모리 내 BM25 인덱스."""

    retriever: BM25Okapi
    documents: List[Document]
    ids: List[str]


@dataclass(slots=True)
class CollectionStats:
    """Chroma 컬렉션 통계를 표현하는 데이터 클래스."""

    vector_count: int
    page_count: int


def _tokenize(text: str) -> List[str]:
    """Tokenize text for BM25 retrieval."""

    return [token.lower() for token in _TOKEN_PATTERN.findall(text or "")]


class ChromaRAGService:
    """Helper responsible for loading, caching and querying Chroma vector stores."""

    def __init__(self) -> None:
        self._storage_root = _DEFAULT_STORAGE_ROOT
        self._storage_root.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self._vectorstores: dict[Tuple[int, str], Chroma] = {}
        self._keyword_indexes: dict[Tuple[int, str], _KeywordIndex] = {}

    def _collection_name(self, workspace_idx: int) -> str:
        return f"workspace-{workspace_idx}"

    def _workspace_directory(self, workspace_name: str) -> Path:
        return ensure_workspace_storage(workspace_name)

    def _resolve_persist_directory(
        self,
        workspace_name: str,
        *,
        storage_uri: Optional[str] = None,
    ) -> Path:
        if storage_uri:
            path = Path(storage_uri)
            path.mkdir(parents=True, exist_ok=True)
            return path
        return self._workspace_directory(workspace_name)

    def _cache_key(
        self,
        workspace_idx: int,
        workspace_name: str,
        *,
        storage_uri: Optional[str] = None,
    ) -> Tuple[int, str]:
        persist_directory = self._resolve_persist_directory(
            workspace_name, storage_uri=storage_uri
        )
        return (workspace_idx, str(persist_directory.resolve()))

    def _create_embeddings(self) -> AzureOpenAIEmbeddings:
        config = _EM_load_azure_openai_config()
        return AzureOpenAIEmbeddings(
            azure_endpoint=config["endpoint"],
            api_key=config["api_key"],
            api_version=config["api_version"],
            azure_deployment=config["deployment"],
            model=config["model"],
        )

    def _get_vectorstore(
        self,
        workspace_idx: int,
        workspace_name: str,
        *,
        storage_uri: Optional[str] = None,
    ) -> Chroma:
        key = self._cache_key(
            workspace_idx, workspace_name, storage_uri=storage_uri
        )
        with self._lock:
            store = self._vectorstores.get(key)
            if store is not None:
                return store
            embeddings = self._create_embeddings()
            persist_directory = key[1]
            store = Chroma(
                collection_name=self._collection_name(workspace_idx),
                embedding_function=embeddings,
                persist_directory=persist_directory,
            )
            self._vectorstores[key] = store
            return store

    def _invalidate_keyword_index(self, key: Tuple[int, str]) -> None:
        with self._lock:
            self._keyword_indexes.pop(key, None)

    def _ensure_keyword_index(
        self,
        workspace_idx: int,
        workspace_name: str,
        *,
        storage_uri: Optional[str] = None,
    ) -> Optional[_KeywordIndex]:
        key = self._cache_key(
            workspace_idx, workspace_name, storage_uri=storage_uri
        )
        with self._lock:
            cached = self._keyword_indexes.get(key)
            if cached is not None:
                return cached

        store = self._get_vectorstore(
            workspace_idx, workspace_name, storage_uri=storage_uri
        )
        raw = store.get(include=["documents", "metadatas"])
        ids = raw.get("ids") or []
        documents = raw.get("documents") or []
        metadatas = raw.get("metadatas") or []
        if not documents:
            return None

        langchain_docs: List[Document] = []
        tokenized_corpus: List[List[str]] = []
        for idx, content in enumerate(documents):
            metadata = dict(metadatas[idx] or {})
            metadata.setdefault("rag_document_id", ids[idx])
            langchain_docs.append(Document(page_content=content, metadata=metadata))
            tokenized_corpus.append(_tokenize(content))

        retriever = BM25Okapi(tokenized_corpus)
        keyword_index = _KeywordIndex(
            retriever=retriever, documents=langchain_docs, ids=list(ids)
        )
        with self._lock:
            self._keyword_indexes[key] = keyword_index
        return keyword_index

    def _prepare_documents(
        self,
        documents: Iterable[Document],
    ) -> Tuple[List[Document], List[str]]:
        """문서 메타데이터를 정규화하고 식별자 목록을 반환한다."""

        normalized: List[Document] = []
        ids: List[str] = []
        for index, doc in enumerate(documents):
            metadata = dict(doc.metadata or {})
            chunk_id = metadata.get("chunk_id")
            rag_id = chunk_id or metadata.get("page_id") or f"{index}-{uuid4()}"
            metadata.setdefault("rag_document_id", rag_id)
            doc.metadata = metadata
            normalized.append(doc)
            ids.append(chunk_id or rag_id)
        return normalized, ids

    def upsert_documents(
        self,
        workspace_idx: int,
        workspace_name: str,
        documents: Iterable[Document],
        *,
        storage_uri: Optional[str] = None,
    ) -> int:
        store = self._get_vectorstore(
            workspace_idx, workspace_name, storage_uri=storage_uri
        )
        docs, ids = self._prepare_documents(documents)
        if not docs:
            return 0

        store.add_documents(documents=docs, ids=ids)
        key = self._cache_key(
            workspace_idx, workspace_name, storage_uri=storage_uri
        )
        self._invalidate_keyword_index(key)
        return len(docs)

    def replace_documents(
        self,
        workspace_idx: int,
        workspace_name: str,
        documents: Iterable[Document],
        *,
        storage_uri: Optional[str] = None,
    ) -> int:
        """특정 페이지와 연관된 기존 청크를 제거한 뒤 새로운 문서를 저장한다."""

        store = self._get_vectorstore(
            workspace_idx, workspace_name, storage_uri=storage_uri
        )
        docs, ids = self._prepare_documents(documents)
        if not docs:
            return 0

        page_ids = {
            str(doc.metadata.get("page_id"))
            for doc in docs
            if doc.metadata and doc.metadata.get("page_id")
        }
        for page_id in page_ids:
            try:
                store.delete(where={"page_id": page_id})
            except Exception:
                # 제거 실패 시에도 이후 add_documents를 시도한다.
                continue

        store.add_documents(documents=docs, ids=ids)
        key = self._cache_key(
            workspace_idx, workspace_name, storage_uri=storage_uri
        )
        self._invalidate_keyword_index(key)
        return len(docs)

    def delete_documents(
        self,
        workspace_idx: int,
        workspace_name: str,
        page_ids: Sequence[str],
        *,
        storage_uri: Optional[str] = None,
    ) -> int:
        """특정 page_id에 해당하는 문서를 제거한다."""

        if not page_ids:
            return 0

        store = self._get_vectorstore(
            workspace_idx, workspace_name, storage_uri=storage_uri
        )
        removed = 0
        for page_id in page_ids:
            try:
                store.delete(where={"page_id": page_id})
                removed += 1
            except Exception:  # pragma: no cover - 삭제 오류는 무시
                continue

        key = self._cache_key(
            workspace_idx, workspace_name, storage_uri=storage_uri
        )
        self._invalidate_keyword_index(key)
        return removed

    def delete_where(
        self,
        workspace_idx: int,
        workspace_name: str,
        *,
        storage_uri: Optional[str] = None,
        where: Optional[Dict[str, Any]] = None,
    ) -> int:
        """메타데이터 조건으로 문서를 제거한다."""

        if not where:
            return 0

        store = self._get_vectorstore(
            workspace_idx, workspace_name, storage_uri=storage_uri
        )
        key = self._cache_key(
            workspace_idx, workspace_name, storage_uri=storage_uri
        )
        try:
            result = store.delete(where=where)
        except Exception as exc:  # pragma: no cover - 삭제 실패 방어
            raise RuntimeError(f"Chroma 문서 삭제 실패: {exc}") from exc

        self._invalidate_keyword_index(key)
        if isinstance(result, dict):
            ids = result.get("ids")
            if isinstance(ids, list):
                return len(ids)
        return 0

    def collection_stats(
        self,
        workspace_idx: int,
        workspace_name: str,
        *,
        storage_uri: Optional[str] = None,
    ) -> CollectionStats:
        """현재 컬렉션의 벡터 수와 페이지 수를 계산한다."""

        store = self._get_vectorstore(
            workspace_idx, workspace_name, storage_uri=storage_uri
        )
        raw = store.get(include=["metadatas"])
        ids = raw.get("ids") or []
        metadatas = raw.get("metadatas") or []
        page_ids = set()
        for metadata in metadatas:
            if isinstance(metadata, dict):
                page_id = metadata.get("page_id")
                if page_id:
                    page_ids.add(str(page_id))
        return CollectionStats(vector_count=len(ids), page_count=len(page_ids))

    def _document_key(self, doc: Document, fallback: int) -> str:
        metadata = doc.metadata or {}
        for key in ("rag_document_id", "chunk_id", "page_id", "source"):
            value = metadata.get(key)
            if value:
                return str(value)
        return f"doc-{fallback}"

    def _rrf_merge(
        self,
        primary: Sequence[Document],
        secondary: Sequence[Document],
        *,
        top_n: int,
        k_rrf: int,
    ) -> List[Tuple[Document, float]]:
        scores: Dict[str, float] = {}
        seen: Dict[str, Document] = {}

        def add_candidates(docs: Sequence[Document]) -> None:
            for rank, doc in enumerate(docs, start=1):
                key = self._document_key(doc, rank)
                seen.setdefault(key, doc)
                scores[key] = scores.get(key, 0.0) + 1.0 / (k_rrf + rank)

        add_candidates(primary)
        add_candidates(secondary)

        ordered_keys = sorted(scores.items(), key=lambda item: item[1], reverse=True)
        merged: List[Tuple[Document, float]] = []
        for key, score in ordered_keys[:top_n]:
            merged.append((seen[key], float(score)))
        return merged

    def hybrid_search_with_score(
        self,
        workspace_idx: int,
        workspace_name: str,
        query: str,
        *,
        k: int = 4,
        storage_uri: Optional[str] = None,
        alpha: float = 0.6,
        candidate_pool: Optional[int] = None,
        rrf_k: int = 60,
    ) -> Sequence[Tuple[Document, float]]:
        final_top_n = max(1, int(k))  # 최종으로 반환할 문서 개수를 최소 1개로 보정
        candidate_pool = candidate_pool or max(final_top_n * 3, 30)  # 초기 후보 풀을 요청 개수 대비 넉넉하게 확보
        candidate_pool = max(candidate_pool, final_top_n)  # 후보 수가 최종 반환 개수보다 작지 않도록 보정

        alpha = max(0.1, min(float(alpha), 0.9))  # 하이브리드 가중치가 극단값을 벗어나지 않도록 제한
        vector_k = max(1, int(round(candidate_pool * alpha)))  # 벡터 검색으로 가져올 문서 수를 가중치 비율로 계산
        keyword_k = max(1, candidate_pool - vector_k)  # 키워드 검색으로 채울 문서 수도 최소 1개로 확보

        store = self._get_vectorstore(
            workspace_idx, workspace_name, storage_uri=storage_uri
        )
        vector_results = store.similarity_search_with_score(query, k=vector_k)

        keyword_results: List[Tuple[Document, float]] = []
        keyword_index = self._ensure_keyword_index(
            workspace_idx, workspace_name, storage_uri=storage_uri
        )
        if keyword_index is not None:
            tokens = _tokenize(query)
            if tokens:
                scores = keyword_index.retriever.get_scores(tokens)
                ranked = sorted(
                    enumerate(scores), key=lambda item: item[1], reverse=True
                )
                for idx, score in ranked:
                    if score <= 0:
                        continue
                    keyword_results.append(
                        (keyword_index.documents[idx], float(score))
                    )
                    if len(keyword_results) >= keyword_k:
                        break

        if not keyword_results:
            return vector_results[:final_top_n]
        if not vector_results:
            return keyword_results[:final_top_n]

        vector_docs = [doc for doc, _ in vector_results]
        keyword_docs = [doc for doc, _ in keyword_results]
        merged = self._rrf_merge(
            vector_docs,
            keyword_docs,
            top_n=candidate_pool,
            k_rrf=max(1, int(rrf_k)),
        )
        return merged[:final_top_n]
