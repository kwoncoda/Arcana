import os
from typing import Dict


def _gpt5_load_chat_config() -> Dict[str, str]:
    """환경 변수에서 Azure GPT5 설정을 불러온다."""

    api_key = os.getenv("GPT5_AZURE_OPENAI_API_KEY")
    endpoint = os.getenv("GPT5_AZURE_OPENAI_ENDPOINT")
    api_version = os.getenv("GPT5_AZURE_OPENAI_API_VERSION")
    deployment = os.getenv("GPT5_AZURE_OPENAI_CHAT_DEPLOYMENT")
    model = os.getenv("GPT5_AZURE_OPENAI_CHAT_MODEL")

    missing = [
        name
        for name, value in [
            ("GPT5_AZURE_OPENAI_API_KEY", api_key),
            ("GPT5_AZURE_OPENAI_ENDPOINT", endpoint),
            ("GPT5_AZURE_OPENAI_API_VERSION", api_version),
            ("GPT5_AZURE_OPENAI_CHAT_DEPLOYMENT", deployment),
        ]
        if not value
    ]
    if missing:
        raise RuntimeError(
            "다음 Azure OpenAI 채팅 환경 변수를 설정하세요: " + ", ".join(missing)
        )

    return {
        "api_key": api_key,
        "endpoint": endpoint,
        "api_version": api_version,
        "deployment": deployment,
        "model": model or deployment,
    }


def _final_answer_load_chat_config() -> Dict[str, str]:
    """최종 답변용 Azure Chat 설정을 불러온다."""

    api_key = os.getenv("FINAL_ANSWER_AZURE_OPENAI_API_KEY")
    endpoint = os.getenv("FINAL_ANSWER_AZURE_OPENAI_ENDPOINT")
    api_version = os.getenv("FINAL_ANSWER_AZURE_OPENAI_API_VERSION")
    deployment = os.getenv("FINAL_ANSWER_AZURE_OPENAI_CHAT_DEPLOYMENT")
    model = os.getenv("FINAL_ANSWER_AZURE_OPENAI_CHAT_MODEL")

    missing = [
        name
        for name, value in [
            ("FINAL_ANSWER_AZURE_OPENAI_API_KEY", api_key),
            ("FINAL_ANSWER_AZURE_OPENAI_ENDPOINT", endpoint),
            ("FINAL_ANSWER_AZURE_OPENAI_API_VERSION", api_version),
            ("FINAL_ANSWER_AZURE_OPENAI_CHAT_DEPLOYMENT", deployment),
        ]
        if not value
    ]
    if missing:
        raise RuntimeError(
            "다음 Azure OpenAI 채팅 환경 변수를 설정하세요: " + ", ".join(missing)
        )

    return {
        "api_key": api_key,
        "endpoint": endpoint,
        "api_version": api_version,
        "deployment": deployment,
        "model": model or deployment,
    }
    

def _decision_load_chat_config() -> Dict[str, str]:
    """환경 변수에서 Azure decision 설정을 불러온다."""

    api_key = os.getenv("DECISION_AZURE_OPENAI_API_KEY")
    endpoint = os.getenv("DECISION_AZURE_OPENAI_ENDPOINT")
    api_version = os.getenv("DECISION_AZURE_OPENAI_API_VERSION")
    deployment = os.getenv("DECISION_AZURE_OPENAI_CHAT_DEPLOYMENT")
    model = os.getenv("DECISION_AZURE_OPENAI_CHAT_MODEL")

    missing = [
        name
        for name, value in [
            ("DECISION_AZURE_OPENAI_API_KEY", api_key),
            ("DECISION_AZURE_OPENAI_ENDPOINT", endpoint),
            ("DECISION_AZURE_OPENAI_API_VERSION", api_version),
            ("DECISION_AZURE_OPENAI_CHAT_DEPLOYMENT", deployment),
        ]
        if not value
    ]
    if missing:
        raise RuntimeError(
            "다음 Azure OpenAI 채팅 환경 변수를 설정하세요: " + ", ".join(missing)
        )

    return {
        "api_key": api_key,
        "endpoint": endpoint,
        "api_version": api_version,
        "deployment": deployment,
        "model": model or deployment,
    }
    

def _EM_load_azure_openai_config() -> dict[str, str]:
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