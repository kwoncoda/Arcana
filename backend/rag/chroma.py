"""Chroma 기반 RAG 적재를 담당하는 서비스 모듈입니다."""  # 모듈 기능을 설명하는 주석

from __future__ import annotations  # 미래 호환성을 위한 __future__ 임포트 주석

import os  # 환경 변수 접근을 위한 os 모듈 임포트 주석
from pathlib import Path  # 경로 조작을 위해 pathlib.Path 사용 주석
from typing import Iterable, List  # 타입 힌트를 위해 typing 모듈에서 Iterable, List 사용 주석

from langchain_chroma import Chroma  # Chroma 벡터 스토어 클래스를 임포트 주석
from langchain_core.documents import Document  # LangChain Document 타입을 임포트 주석
from langchain_openai import AzureOpenAIEmbeddings  # Azure OpenAI 임베딩 클래스를 임포트 주석

from utils.workspace_storage import (  # 워크스페이스별 스토리지 경로 유틸리티 임포트 주석
    ensure_workspace_storage,
    workspace_storage_path,
)

_DEFAULT_STORAGE_ROOT = workspace_storage_path("_").parent  # 기본 RAG 스토리지 루트를 정의하는 주석


def _load_azure_openai_config() -> dict[str, str]:  # Azure OpenAI 설정을 로드하는 헬퍼 함수 정의 주석
    """Azure OpenAI 임베딩 호출에 필요한 환경 변수를 검증하고 반환합니다."""  # 함수 역할을 설명하는 주석

    api_key = os.getenv("EM_AZURE_OPENAI_API_KEY")  # Azure OpenAI API 키를 환경 변수에서 읽는 주석
    endpoint = os.getenv("EM_AZURE_OPENAI_ENDPOINT")  # Azure OpenAI 엔드포인트를 환경 변수에서 읽는 주석
    api_version = os.getenv("EM_AZURE_OPENAI_API_VERSION")  # Azure OpenAI API 버전을 환경 변수에서 읽는 주석
    deployment = os.getenv("EM_AZURE_OPENAI_EMBEDDING_DEPLOYMENT")  # 임베딩 배포 이름을 환경 변수에서 읽는 주석

    missing = [  # 누락된 환경 변수를 추적하기 위한 리스트 생성 주석
        name
        for name, value in [  # 각 환경 변수의 존재 여부를 점검하는 리스트 컴프리헨션 주석
            ("EM_AZURE_OPENAI_API_KEY", api_key),
            ("EM_AZURE_OPENAI_ENDPOINT", endpoint),
            ("EM_AZURE_OPENAI_API_VERSION", api_version),
            ("EM_AZURE_OPENAI_EMBEDDING_DEPLOYMENT", deployment),
        ]
        if not value  # 값이 비어있는 경우에만 리스트에 포함하는 조건 주석
    ]

    if missing:  # 필수 환경 변수가 하나라도 누락된 경우 확인 주석
        joined = ", ".join(missing)  # 누락된 환경 변수 이름을 문자열로 결합 주석
        raise RuntimeError(f"다음 Azure OpenAI 환경 변수가 필요합니다: {joined}")  # 예외를 발생시켜 누락을 알리는 주석

    return {  # 유효한 설정 값을 딕셔너리로 반환하는 주석
        "api_key": api_key,
        "endpoint": endpoint,
        "api_version": api_version,
        "deployment": deployment,
    }


class ChromaRAGService:  # Chroma 기반 RAG 서비스를 위한 클래스 정의 주석
    """Chroma 벡터 스토어에 문서를 적재하는 헬퍼입니다."""  # 클래스 역할 설명 주석

    def __init__(self) -> None:  # 초기화 메서드 정의 주석
        self._storage_root = _DEFAULT_STORAGE_ROOT  # 기본 스토리지 디렉터리를 Path로 저장하는 주석
        self._storage_root.mkdir(parents=True, exist_ok=True)  # 스토리지 루트 디렉터리를 미리 생성하는 주석
        self._vectorstores: dict[int, Chroma] = {}  # 워크스페이스별 Chroma 인스턴스 캐시 딕셔너리 초기화 주석

    def _collection_name(self, workspace_idx: int) -> str:  # 컬렉션 이름을 생성하는 내부 메서드 정의 주석
        return f"workspace-{workspace_idx}"  # 워크스페이스 식별자를 포함한 컬렉션 이름 반환 주석

    def _workspace_directory(self, workspace_name: str) -> Path:  # 워크스페이스 전용 디렉터리를 반환하는 내부 메서드 주석
        return ensure_workspace_storage(workspace_name)  # 유틸을 통해 워크스페이스 디렉터리를 생성/반환하는 주석

    def _create_embeddings(self) -> AzureOpenAIEmbeddings:  # Azure OpenAI 임베딩 인스턴스를 생성하는 내부 메서드 정의 주석
        config = _load_azure_openai_config()  # Azure OpenAI 설정을 로드하는 주석
        return AzureOpenAIEmbeddings(  # 설정 값을 사용해 임베딩 객체를 생성하고 반환하는 주석
            azure_endpoint=config["endpoint"],  # Azure 엔드포인트를 매개변수로 전달하는 주석
            api_key=config["api_key"],  # API 키를 매개변수로 전달하는 주석
            api_version=config["api_version"],  # API 버전을 매개변수로 전달하는 주석
            azure_deployment=config["deployment"],  # 임베딩 배포 이름을 매개변수로 전달하는 주석
        )

    def _get_vectorstore(self, workspace_idx: int, workspace_name: str) -> Chroma:  # 워크스페이스별 Chroma 인스턴스를 반환하는 내부 메서드 주석
        store = self._vectorstores.get(workspace_idx)  # 캐시에서 기존 인스턴스를 조회하는 주석
        if store:  # 캐시에 인스턴스가 존재하면 반환하는 조건 주석
            return store  # 기존 스토어를 반환하는 주석

        persist_directory = self._workspace_directory(workspace_name)  # 워크스페이스 전용 디렉터리를 가져오는 주석
        embeddings = self._create_embeddings()  # 임베딩 인스턴스를 생성하는 주석
        store = Chroma(  # 새로운 Chroma 인스턴스를 생성하는 주석
            collection_name=self._collection_name(workspace_idx),  # 컬렉션 이름 지정 주석
            embedding_function=embeddings,  # 임베딩 함수를 설정하는 주석
            persist_directory=str(persist_directory),  # 지속 디렉터리를 문자열로 전달하는 주석
        )
        self._vectorstores[workspace_idx] = store  # 생성한 스토어를 캐시에 저장하는 주석
        return store  # 새로 생성한 스토어를 반환하는 주석

    def upsert_documents(
        self,
        workspace_idx: int,
        workspace_name: str,
        documents: Iterable[Document],
    ) -> int:  # 문서를 추가하는 공개 메서드 정의 주석
        store = self._get_vectorstore(workspace_idx, workspace_name)  # 대상 워크스페이스의 스토어를 가져오는 주석
        docs: List[Document] = list(documents)  # 입력 이터러블을 리스트로 변환해 보관하는 주석
        if not docs:  # 문서가 비어있는 경우 조기 종료 조건 주석
            return 0  # 추가된 문서 수 0을 반환하는 주석

        ids = [doc.metadata.get("chunk_id") for doc in docs]  # 각 문서의 chunk_id를 추출하는 주석
        store.add_documents(documents=docs, ids=ids)  # Chroma에 문서를 추가하는 주석
        store.persist()  # 변경 사항을 디스크에 저장하는 주석
        return len(docs)  # 추가된 문서 수를 반환하는 주석
