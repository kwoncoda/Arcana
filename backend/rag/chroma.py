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
from langchain_core.vectorstores import VectorStoreRetriever
from langchain_openai import AzureOpenAIEmbeddings
from rank_bm25 import BM25Okapi

from utils.workspace_storage import ensure_workspace_storage, workspace_storage_path

_DEFAULT_STORAGE_ROOT = workspace_storage_path("_").parent
_TOKEN_PATTERN = re.compile(r"[\w가-힣]+", re.UNICODE)


@dataclass(slots=True)
class _KeywordIndex:
    """키워드 검색을 위한 메모리 내 BM25 인덱스."""

    retriever: BM25Okapi
    documents: List[Document]
    ids: List[str]


def _load_azure_openai_config() -> dict[str, str]:
    """Azure OpenAI 임베딩 구성을 로드하고 검증"""

    api_key = os.getenv("EM_AZURE_OPENAI_API_KEY")
    endpoint = os.getenv("EM_AZURE_OPENAI_ENDPOINT")
    api_version = os.getenv("EM_AZURE_OPENAI_API_VERSION")
    deployment = os.getenv("EM_AZURE_OPENAI_EMBEDDING_DEPLOYMENT")
    model = os.getenv("EM_AZURE_OPENAI_EMBEDDING_MODEL")

    missing = [
        name
        for name, value in [
            ("EM_AZURE_OPENAI_API_KEY", api_key),
            ("EM_AZURE_OPENAI_ENDPOINT", endpoint),
            ("EM_AZURE_OPENAI_API_VERSION", api_version),
            ("EM_AZURE_OPENAI_EMBEDDING_DEPLOYMENT", deployment),
        ]
        if not value
    ]
    if missing:
        raise RuntimeError(
            "다음 Azure OpenAI 환경 변수가 필요합니다: " + ", ".join(missing)
        )

    return {
        "api_key": api_key,
        "endpoint": endpoint,
        "api_version": api_version,
        "deployment": deployment,
        "model": model or deployment,
    }


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
        config = _load_azure_openai_config()
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
        raw = store.get(include=["documents", "metadatas", "ids"])
        documents = raw.get("documents") or []
        metadatas = raw.get("metadatas") or []
        ids = raw.get("ids") or []
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
        docs: List[Document] = list(documents)
        if not docs:
            return 0

        ids: List[str] = []
        for index, doc in enumerate(docs):
            metadata = dict(doc.metadata or {})
            chunk_id = metadata.get("chunk_id")
            rag_id = chunk_id or metadata.get("page_id") or f"{index}-{uuid4()}"
            metadata.setdefault("rag_document_id", rag_id)
            doc.metadata = metadata
            ids.append(chunk_id or rag_id)

        store.add_documents(documents=docs, ids=ids)
        key = self._cache_key(
            workspace_idx, workspace_name, storage_uri=storage_uri
        )
        self._invalidate_keyword_index(key)
        return len(docs)

    def get_retriever(
        self,
        workspace_idx: int,
        workspace_name: str,
        *,
        storage_uri: Optional[str] = None,
        search_type: str = "similarity",
        search_kwargs: Optional[dict[str, Any]] = None,
    ) -> VectorStoreRetriever:
        store = self._get_vectorstore(
            workspace_idx, workspace_name, storage_uri=storage_uri
        )
        effective_kwargs: dict[str, Any] = dict(search_kwargs or {})
        effective_kwargs.setdefault("k", 4)
        return store.as_retriever(
            search_type=search_type, search_kwargs=effective_kwargs
        )

    def similarity_search_with_score(
        self,
        workspace_idx: int,
        workspace_name: str,
        query: str,
        *,
        k: int = 4,
        storage_uri: Optional[str] = None,
        retriever: Optional[VectorStoreRetriever] = None,
    ) -> Sequence[Tuple[Document, float]]:
        if retriever is not None:
            store = retriever.vectorstore
            effective_k = getattr(retriever, "search_kwargs", {}).get("k", k)
        else:
            store = self._get_vectorstore(
                workspace_idx, workspace_name, storage_uri=storage_uri
            )
            effective_k = k
        return store.similarity_search_with_score(query, k=effective_k)

    def keyword_search_with_score(
        self,
        workspace_idx: int,
        workspace_name: str,
        query: str,
        *,
        k: int = 4,
        storage_uri: Optional[str] = None,
    ) -> Sequence[Tuple[Document, float]]:
        keyword_index = self._ensure_keyword_index(
            workspace_idx, workspace_name, storage_uri=storage_uri
        )
        if keyword_index is None:
            return []

        tokens = _tokenize(query)
        if not tokens:
            return []

        scores = keyword_index.retriever.get_scores(tokens)
        ranked = sorted(
            enumerate(scores), key=lambda item: item[1], reverse=True
        )
        results: List[Tuple[Document, float]] = []
        for idx, score in ranked:
            if score <= 0:
                continue
            results.append((keyword_index.documents[idx], float(score)))
            if len(results) >= k:
                break
        return results

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
        final_top_n = max(1, int(k))
        candidate_pool = candidate_pool or max(final_top_n * 3, 30)
        candidate_pool = max(candidate_pool, final_top_n)

        alpha = max(0.1, min(float(alpha), 0.9))
        vector_k = max(1, int(round(candidate_pool * alpha)))
        keyword_k = max(1, candidate_pool - vector_k)

        vector_results = self.similarity_search_with_score(
            workspace_idx,
            workspace_name,
            query,
            k=vector_k,
            storage_uri=storage_uri,
        )
        keyword_results = self.keyword_search_with_score(
            workspace_idx,
            workspace_name,
            query,
            k=keyword_k,
            storage_uri=storage_uri,
        )

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
