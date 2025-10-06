"""Notion 페이지 데이터를 전처리하고 RAG 문서로 변환하는 모듈입니다."""  # 모듈 기능 설명 주석

from __future__ import annotations  # 미래 호환성을 위한 __future__ 임포트 주석

from copy import deepcopy  # 메타데이터 복제를 위한 deepcopy 임포트 주석
from typing import Any, Dict, Iterable, List  # 타입 힌트를 위한 typing 모듈 임포트 주석

from langchain_core.documents import Document  # LangChain 문서 타입 임포트 주석


def _clean_text_lines(lines: Iterable[str]) -> List[str]:  # 텍스트 라인 정제를 수행하는 함수 정의 주석
    """문자열 이터러블에서 공백 라인을 제거하고 정제된 리스트를 반환합니다."""  # 함수 목적 설명 주석

    cleaned: List[str] = []  # 정제된 텍스트를 누적할 리스트 초기화 주석
    for line in lines:  # 각 입력 라인을 순회하는 루프 주석
        if not isinstance(line, str):  # 라인이 문자열인지 확인하는 조건 주석
            continue  # 문자열이 아니면 건너뛰기 주석
        stripped = line.strip()  # 좌우 공백을 제거한 문자열 생성 주석
        if stripped:  # 공백 제거 후 내용이 남아 있는지 확인하는 조건 주석
            cleaned.append(stripped)  # 유효한 라인을 결과 리스트에 추가 주석
    return cleaned  # 정제된 문자열 리스트 반환 주석


def _gather_block_text(block: Dict[str, Any]) -> List[str]:  # 블록에서 모든 텍스트를 재귀적으로 수집하는 함수 정의 주석
    text_lines = _clean_text_lines(block.get("text", []))  # 현재 블록의 텍스트 라인을 정제해 가져오는 주석
    for child in block.get("children", []):  # 자식 블록을 순회하는 루프 주석
        text_lines.extend(_gather_block_text(child))  # 자식 블록의 텍스트를 누적 리스트에 추가 주석
    return text_lines  # 누적된 텍스트 라인 리스트 반환 주석


def _combine_page_text(blocks: Iterable[Dict[str, Any]]) -> List[str]:  # 페이지 블록들의 텍스트를 합치는 함수 정의 주석
    combined: List[str] = []  # 페이지 전체 텍스트를 담을 리스트 초기화 주석
    for block in blocks:  # 각 블록을 순회하는 루프 주석
        combined.extend(_gather_block_text(block))  # 블록에서 추출한 텍스트를 누적 리스트에 추가 주석
    return combined  # 페이지 전체 텍스트 라인 리스트 반환 주석


def _resolve_page_url(page: Dict[str, Any]) -> str:  # 노션 페이지 URL을 결정하는 함수 정의 주석
    explicit_url = page.get("url")  # 페이지 데이터에서 직접 제공된 URL 조회 주석
    if isinstance(explicit_url, str) and explicit_url.strip():  # URL이 문자열이고 비어있지 않은지 확인 주석
        return explicit_url.strip()  # 정제된 URL을 그대로 반환 주석

    page_id = str(page.get("page_id", "")).replace("-", "")  # 페이지 ID에서 하이픈을 제거해 정규화 주석
    return f"https://www.notion.so/{page_id}"  # Notion 표준 URL 형식으로 변환해 반환 주석


def _chunk_text(text: str, *, chunk_size: int, chunk_overlap: int) -> List[str]:  # 긴 텍스트를 분할하는 함수 정의 주석
    if chunk_size <= 0:  # 청크 크기가 0 이하인 경우 확인 주석
        return [text] if text else []  # 원본 텍스트 또는 빈 리스트 반환 주석

    if chunk_overlap >= chunk_size:  # 중첩 길이가 청크 크기 이상인지 확인 주석
        chunk_overlap = max(0, chunk_size - 1)  # 중첩 길이를 안전한 범위로 조정 주석

    chunks: List[str] = []  # 분할된 텍스트를 담을 리스트 초기화 주석
    start = 0  # 현재 청크 시작 인덱스 초기화 주석
    text_length = len(text)  # 전체 텍스트 길이 계산 주석

    while start < text_length:  # 전체 텍스트를 순회하는 루프 주석
        end = min(start + chunk_size, text_length)  # 현재 청크의 끝 인덱스 계산 주석
        chunk = text[start:end].strip()  # 현재 구간의 텍스트를 잘라 공백 제거 주석
        if chunk:  # 잘린 텍스트가 비어있지 않은지 확인 주석
            chunks.append(chunk)  # 유효한 청크를 결과 리스트에 추가 주석
        if end == text_length:  # 텍스트 끝에 도달했는지 확인 주석
            break  # 루프 종료 주석
        start = max(end - chunk_overlap, start + 1)  # 다음 청크 시작 위치 계산 주석
    return chunks  # 분할된 텍스트 청크 리스트 반환 주석


def build_jsonl_records_from_pages(  # 페이지 데이터를 JSONL 레코드로 변환하는 함수 정의 주석
    pages: List[Dict[str, Any]],  # 노션 페이지 리스트 파라미터 주석
    *,
    chunk_size: int = 1200,  # 청크 크기 기본값을 지정하는 키워드 인자 주석
    chunk_overlap: int = 200,  # 청크 중첩 길이 기본값을 지정하는 키워드 인자 주석
) -> List[Dict[str, str]]:  # JSONL 레코드 리스트를 반환함을 명시하는 주석
    records: List[Dict[str, str]] = []  # 결과 레코드 리스트 초기화 주석
    for page in pages:  # 각 페이지를 순회하는 루프 주석
        page_id = str(page.get("page_id"))  # 페이지 ID를 문자열로 변환해 추출 주석
        title = str(page.get("title") or "")  # 페이지 제목을 문자열로 정규화 주석
        last_edited_time = str(page.get("last_edited_time") or "")  # 수정 시각을 문자열로 정규화 주석
        page_url = _resolve_page_url(page)  # 페이지 URL을 계산하는 주석

        text_lines = _combine_page_text(page.get("blocks", []))  # 페이지 블록에서 텍스트 라인 추출 주석
        if not text_lines:  # 텍스트가 존재하지 않는 경우 확인 주석

            record = {  # 내용이 비어 있는 페이지도 추적하기 위한 레코드 생성 주석
                "page_id": page_id,  # 페이지 식별자를 레코드에 저장 주석
                "title": title,  # 페이지 제목을 레코드에 저장 주석
                "last_edited_time": last_edited_time,  # 페이지 수정 시각을 레코드에 저장 주석
                "text": "",  # 비어 있는 텍스트를 명시적으로 기록 주석
                "page_url": page_url,  # 페이지 URL을 레코드에 저장 주석
            }
            records.append(record)  # 비어 있는 페이지 레코드를 결과 리스트에 추가 주석

            continue  # 다음 페이지로 건너뛰기 주석

        full_text = "\n".join(text_lines)  # 라인들을 줄바꿈으로 결합해 전체 텍스트 생성 주석
        for chunk in _chunk_text(full_text, chunk_size=chunk_size, chunk_overlap=chunk_overlap):  # 텍스트를 청크 단위로 분할하는 루프 주석
            record = {  # JSONL 한 줄에 해당하는 레코드 딕셔너리 생성 주석
                "page_id": page_id,  # 페이지 식별자를 레코드에 저장 주석
                "title": title,  # 페이지 제목을 레코드에 저장 주석
                "last_edited_time": last_edited_time,  # 페이지 수정 시각을 레코드에 저장 주석
                "text": chunk,  # 분할된 텍스트 청크를 레코드에 저장 주석
                "page_url": page_url,  # 페이지 URL을 레코드에 저장 주석
            }
            records.append(record)  # 생성한 레코드를 결과 리스트에 추가 주석
    return records  # 구축된 JSONL 레코드 리스트 반환 주석


def build_documents_from_records(  # JSONL 레코드를 LangChain 문서로 변환하는 함수 정의 주석
    records: List[Dict[str, str]],  # JSONL 레코드 리스트 파라미터 주석
    workspace_metadata: Dict[str, Any],  # 워크스페이스 메타데이터 파라미터 주석
) -> List[Document]:  # LangChain 문서 리스트 반환을 명시하는 주석
    documents: List[Document] = []  # 결과 문서 리스트 초기화 주석
    for index, record in enumerate(records):  # 각 레코드를 순회하며 인덱스를 추적하는 루프 주석
        text = record.get("text", "")  # 레코드에서 텍스트 내용을 추출하는 주석
        if not text:  # 비어 있는 텍스트 청크인지 확인하는 주석
            continue  # 비어 있는 청크는 RAG 문서로 변환하지 않고 건너뛰는 주석

        metadata = deepcopy(workspace_metadata)  # 워크스페이스 메타데이터를 복제해 독립본 생성 주석
        metadata.update(  # 페이지 및 청크 정보를 메타데이터에 병합하는 주석
            {
                "page_id": record.get("page_id"),  # 페이지 ID를 메타데이터에 저장 주석
                "page_title": record.get("title"),  # 페이지 제목을 메타데이터에 저장 주석
                "page_url": record.get("page_url"),  # 페이지 URL을 메타데이터에 저장 주석
                "last_edited_time": record.get("last_edited_time"),  # 수정 시각을 메타데이터에 저장 주석
                "chunk_id": f"{record.get('page_id')}:{index}",  # 페이지 ID와 인덱스로 청크 ID 생성 주석
                "chunk_index": index,  # 청크 인덱스를 메타데이터에 저장 주석
            }
        )
        document = Document(page_content=text, metadata=metadata)  # 레코드 텍스트와 메타데이터로 문서 생성 주석
        documents.append(document)  # 생성된 문서를 결과 리스트에 추가 주석
    return documents  # 생성된 문서 리스트 반환 주석


def build_documents_from_pages(  # 페이지 데이터에서 직접 문서를 생성하는 편의 함수 정의 주석
    pages: List[Dict[str, Any]],  # 노션 페이지 리스트 파라미터 주석
    workspace_metadata: Dict[str, Any],  # 워크스페이스 메타데이터 파라미터 주석
    *,
    chunk_size: int = 1200,  # 청크 크기 기본값을 지정하는 키워드 인자 주석
    chunk_overlap: int = 200,  # 청크 중첩 길이 기본값을 지정하는 키워드 인자 주석
) -> List[Document]:  # LangChain 문서 리스트 반환을 명시하는 주석
    records = build_jsonl_records_from_pages(  # 페이지에서 JSONL 레코드를 생성하는 헬퍼 호출 주석
        pages,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
    return build_documents_from_records(records, workspace_metadata)  # 레코드 리스트를 문서로 변환해 반환 주석
