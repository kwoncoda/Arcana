"""Utilities for fetching and transforming Google Drive files for RAG."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import httpx
import tiktoken
from langchain_core.documents import Document
from pypdf import PdfReader


FILES_ENDPOINT = "https://www.googleapis.com/drive/v3/files"

logger = logging.getLogger(__name__)

_DEFAULT_FIELDS = (
    "nextPageToken, files(id, name, mimeType, modifiedTime, webViewLink,"
    " size, capabilities/canDownload)"
)

_CONVERTIBLE_MIME_TYPES = {
    "application/vnd.google-apps.document",
    "application/vnd.google-apps.spreadsheet",
    "application/vnd.google-apps.presentation",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}

_GOOGLE_NATIVE_MIME_TYPES = {
    "application/vnd.google-apps.document",
    "application/vnd.google-apps.spreadsheet",
    "application/vnd.google-apps.presentation",
}

_OFFICE_TO_GOOGLE_MIME_MAP = {
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "application/vnd.google-apps.document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "application/vnd.google-apps.spreadsheet",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": "application/vnd.google-apps.presentation",
}

_HWP_MIME_TYPES = {"application/x-hwp", "application/haansoft-hwp"}

_ENC = tiktoken.get_encoding("cl100k_base")

_DEFAULT_CHUNK_SIZE = 800
_DEFAULT_CHUNK_OVERLAP_RATIO = 0.1

_PDF_EXPORT_MIME = "application/pdf"

_FILENAME_SANITIZE_PATTERN = re.compile(r"[^\w .-]+", re.UNICODE)


# 외부 모듈에서 사용할 수 있도록 공개 상수로 재노출한다.
CONVERTIBLE_MIME_TYPES = frozenset(_CONVERTIBLE_MIME_TYPES)
GOOGLE_NATIVE_MIME_TYPES = frozenset(_GOOGLE_NATIVE_MIME_TYPES)


class GoogleDriveAPIError(RuntimeError):
    """Raised when the Google Drive API responds with an unexpected error."""


class UnsupportedGoogleDriveFile(RuntimeError):
    """Raised when a Google Drive file type cannot be processed."""


@dataclass(slots=True)
class GoogleDriveFile:
    """Container for the textual representation of a Google Drive file."""

    file_id: str
    name: str
    mime_type: str
    modified_time: str
    web_view_link: Optional[str]
    text: str
    format: str
    pdf_path: Path


def _format_datetime_for_query(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    else:
        value = value.astimezone(timezone.utc)
    return value.isoformat().replace("+00:00", "Z")


async def _list_files(
    client: httpx.AsyncClient,
    *,
    access_token: str,
    modified_after: Optional[datetime] = None,
) -> List[Dict[str, str]]:
    headers = {"Authorization": f"Bearer {access_token}"}
    convertible_query = "(" + " or ".join(
        f"mimeType = '{mime}'" for mime in sorted(_CONVERTIBLE_MIME_TYPES)
    ) + ")"

    params = {
        "pageSize": 200,
        "fields": _DEFAULT_FIELDS,
        "supportsAllDrives": "false",
        "includeItemsFromAllDrives": "false",
        "orderBy": "modifiedTime desc",
        "q": " and ".join(
            filter(
                None,
                [
                    "trashed=false",
                    "mimeType != 'application/vnd.google-apps.folder'",
                    "'me' in owners",
                    convertible_query,
                    (
                        f"modifiedTime > '{_format_datetime_for_query(modified_after)}'"
                        if modified_after
                        else None
                    ),
                ],
            )
        ),
    }

    files: List[Dict[str, str]] = []
    page_token: Optional[str] = None

    while True:
        if page_token:
            params["pageToken"] = page_token
        else:
            params.pop("pageToken", None)

        response = await client.get(FILES_ENDPOINT, headers=headers, params=params)
        if response.status_code == 401:
            raise GoogleDriveAPIError("Google Drive 접근 권한이 만료되었습니다.")
        if response.status_code != 200:
            raise GoogleDriveAPIError(response.text)

        payload = response.json()
        files.extend(payload.get("files", []))
        page_token = payload.get("nextPageToken")
        if not page_token:
            break

    return files


def _sanitize_filename(name: str) -> str:
    sanitized = _FILENAME_SANITIZE_PATTERN.sub("_", name.strip())
    sanitized = sanitized.strip(" ._-")
    return sanitized or "document"


def _write_pdf(download_dir: Path, name: str, file_id: str, content: bytes) -> Path:
    download_dir.mkdir(parents=True, exist_ok=True)
    base_name = _sanitize_filename(name) or "document"
    filename = f"{base_name}-{file_id}.pdf"
    path = download_dir / filename
    path.write_bytes(content)
    logger.info("Google Drive 파일 '%s'을(를) PDF로 저장했습니다: %s", name, path)
    return path


def _extract_pdf_text(pdf_path: Path) -> str:
    try:
        reader = PdfReader(str(pdf_path))
    except Exception as exc:  # pragma: no cover - PDF 파서 방어
        raise UnsupportedGoogleDriveFile(f"PDF를 열 수 없습니다: {exc}") from exc

    texts: List[str] = []
    for index, page in enumerate(reader.pages):
        try:
            extracted = page.extract_text() or ""
        except Exception as exc:  # pragma: no cover - PDF 파서 방어
            logger.warning(
                "PDF 페이지(%s, %s) 텍스트 추출에 실패했습니다: %s",
                pdf_path.name,
                index,
                exc,
            )
            extracted = ""
        if extracted.strip():
            texts.append(extracted.strip())

    combined = "\n\n".join(texts).strip()
    if not combined:
        logger.warning("PDF에서 추출된 텍스트가 없습니다: %s", pdf_path)
    return combined


async def _copy_file_as_google_type(
    client: httpx.AsyncClient,
    *,
    file_id: str,
    target_mime: str,
    headers: Dict[str, str],
    original_name: str,
) -> str:
    logger.info(
        "Google Drive 파일 '%s'을(를) '%s' 형식으로 임시 변환합니다.",
        original_name,
        target_mime,
    )
    body = {
        "mimeType": target_mime,
        "name": f"[Arcana Temp] {original_name}",
        "parents": ["root"],
    }
    response = await client.post(
        f"{FILES_ENDPOINT}/{file_id}/copy",
        headers=headers,
        json=body,
    )
    if response.status_code != 200:
        raise GoogleDriveAPIError(response.text)
    payload = response.json()
    temp_id = payload.get("id")
    if not temp_id:
        raise GoogleDriveAPIError("임시 Google 문서 ID를 가져오지 못했습니다.")
    return temp_id


async def _delete_temporary_file(
    client: httpx.AsyncClient,
    *,
    file_id: str,
    headers: Dict[str, str],
) -> None:
    try:
        response = await client.delete(
            f"{FILES_ENDPOINT}/{file_id}",
            headers=headers,
        )
        if response.status_code not in {200, 204}:
            logger.warning(
                "임시 Google 문서를 삭제하지 못했습니다(%s): %s",
                file_id,
                response.text,
            )
    except Exception as exc:  # pragma: no cover - 방어적 로깅
        logger.warning("임시 Google 문서 삭제 중 오류(%s): %s", file_id, exc)


async def _download_file_as_pdf(
    client: httpx.AsyncClient,
    *,
    file: Dict[str, str],
    headers: Dict[str, str],
    download_dir: Path,
) -> Tuple[Path, str]:
    file_id = file.get("id") or ""
    mime_type = file.get("mimeType") or ""
    name = file.get("name") or ""

    if not file_id:
        raise GoogleDriveAPIError("파일 ID가 없습니다.")

    if mime_type in _HWP_MIME_TYPES or name.lower().endswith(".hwp"):
        raise UnsupportedGoogleDriveFile("한글(.hwp) 파일은 지원하지 않습니다.")

    temporary_id: Optional[str] = None
    export_source_id = file_id

    if mime_type in _GOOGLE_NATIVE_MIME_TYPES:
        logger.info("Google Drive 파일 '%s'을(를) PDF로 내보냅니다.", name)
    elif mime_type in _OFFICE_TO_GOOGLE_MIME_MAP:
        target_mime = _OFFICE_TO_GOOGLE_MIME_MAP[mime_type]
        temporary_id = await _copy_file_as_google_type(
            client,
            file_id=file_id,
            target_mime=target_mime,
            headers=headers,
            original_name=name,
        )
        export_source_id = temporary_id
    else:
        raise UnsupportedGoogleDriveFile(
            f"지원하지 않는 Google Drive 파일 형식입니다: {mime_type}"
        )

    try:
        response = await client.get(
            f"{FILES_ENDPOINT}/{export_source_id}/export",
            headers=headers,
            params={"mimeType": _PDF_EXPORT_MIME},
        )
        if response.status_code != 200:
            raise GoogleDriveAPIError(response.text)
        pdf_path = _write_pdf(download_dir, name, file_id, response.content)
    finally:
        if temporary_id:
            await _delete_temporary_file(client, file_id=temporary_id, headers=headers)

    return pdf_path, "pdf"


def _chunk_text(
    text: str,
    *,
    chunk_size: int = _DEFAULT_CHUNK_SIZE,
    overlap_ratio: float = _DEFAULT_CHUNK_OVERLAP_RATIO,
) -> List[str]:
    if not text:
        return []

    tokens = _ENC.encode(text)
    if not tokens:
        return []

    overlap = int(chunk_size * overlap_ratio)
    if overlap >= chunk_size:
        overlap = max(0, chunk_size - 1)

    chunks: List[str] = []
    start = 0
    total = len(tokens)

    while start < total:
        end = min(total, start + chunk_size)
        chunk_tokens = tokens[start:end]
        chunks.append(_ENC.decode(chunk_tokens))
        if end >= total:
            break
        start = end - overlap if overlap > 0 else end

    return chunks


def _build_records_from_file(
    file: GoogleDriveFile,
    *,
    chunk_size: int = _DEFAULT_CHUNK_SIZE,
    overlap_ratio: float = _DEFAULT_CHUNK_OVERLAP_RATIO,
) -> List[Dict[str, str]]:
    records: List[Dict[str, str]] = []
    chunks = _chunk_text(file.text, chunk_size=chunk_size, overlap_ratio=overlap_ratio)

    if not chunks:
        records.append(
            {
                "file_id": file.file_id,
                "title": file.name,
                "modified_time": file.modified_time,
                "url": file.web_view_link or "",
                "mime_type": file.mime_type,
                "text": "",
                "plain_text": "",
                "format": file.format,
                "pdf_path": str(file.pdf_path),
                "chunk_index": 0,
            }
        )
        return records

    for chunk_index, chunk in enumerate(chunks):
        records.append(
            {
                "file_id": file.file_id,
                "title": file.name,
                "modified_time": file.modified_time,
                "url": file.web_view_link or "",
                "mime_type": file.mime_type,
                "text": chunk,
                "plain_text": chunk,
                "format": file.format,
                "pdf_path": str(file.pdf_path),
                "chunk_index": chunk_index,
            }
        )

    return records


def build_records_from_files(
    files: Sequence[GoogleDriveFile],
    *,
    chunk_size: int = _DEFAULT_CHUNK_SIZE,
    overlap_ratio: float = _DEFAULT_CHUNK_OVERLAP_RATIO,
) -> List[Dict[str, str]]:
    records: List[Dict[str, str]] = []
    for file in files:
        records.extend(
            _build_records_from_file(
                file, chunk_size=chunk_size, overlap_ratio=overlap_ratio
            )
        )
    return records


def build_documents_from_records(
    records: Sequence[Dict[str, str]],
    workspace_metadata: Dict[str, str],
) -> List[Document]:
    documents: List[Document] = []
    for index, record in enumerate(records):
        plain_text = record.get("plain_text") or ""
        formatted_text = record.get("text") or plain_text
        if not plain_text.strip():
            continue

        metadata = dict(workspace_metadata)
        file_id = record.get("file_id") or ""
        chunk_index = record.get("chunk_index")
        if isinstance(chunk_index, int):
            chunk_number = chunk_index
        else:
            chunk_number = index
        metadata.update(
            {
                "page_id": file_id,
                "page_title": record.get("title"),
                "page_url": record.get("url"),
                "last_edited_time": record.get("modified_time"),
                "chunk_id": f"{file_id}:{chunk_number}",
                "chunk_index": chunk_number,
                "format": record.get("format", "text"),
                "formatted_text": formatted_text,
                "plain_text": plain_text,
                "provider": "googledrive",
                "file_id": file_id,
                "file_mime_type": record.get("mime_type"),
                "pdf_path": record.get("pdf_path"),
            }
        )
        documents.append(Document(page_content=plain_text, metadata=metadata))
    return documents


async def fetch_authorized_text_files(
    access_token: str,
    *,
    modified_after: Optional[datetime] = None,
    download_dir: Path,
    files_override: Optional[Sequence[Dict[str, str]]] = None,
) -> Tuple[List[GoogleDriveFile], List[Dict[str, str]]]:
    async with httpx.AsyncClient(timeout=60) as client:
        if files_override is not None:
            raw_files = list(files_override)
            logger.info(
                "사전 계산된 Google Drive 파일 %d건에 대해 변환을 진행합니다.",
                len(raw_files),
            )
        else:
            raw_files = await _list_files(
                client, access_token=access_token, modified_after=modified_after
            )

            logger.info(
                "Google Drive에서 %d개의 변환 대상 파일을 찾았습니다.", len(raw_files)
            )

        headers = {"Authorization": f"Bearer {access_token}"}
        converted: List[GoogleDriveFile] = []
        skipped: List[Dict[str, str]] = []

        for index, file in enumerate(raw_files, start=1):
            file_id = file.get("id") or ""
            name = file.get("name") or ""
            mime_type = file.get("mimeType") or ""
            logger.info(
                "(%d/%d) Google Drive 파일 동기화 시작: %s (%s)",
                index,
                len(raw_files),
                name,
                file_id,
            )

            capabilities = file.get("capabilities") or {}
            can_download = capabilities.get("canDownload", True)
            if not can_download:
                skipped.append(
                    {
                        "file_id": file_id,
                        "name": name,
                        "mime_type": mime_type,
                        "reason": "다운로드 권한이 없습니다.",
                    }
                )
                logger.info("파일 '%s'은(는) 다운로드 권한이 없어 건너뜁니다.", name)
                continue

            try:
                pdf_path, fmt = await _download_file_as_pdf(
                    client,
                    file=file,
                    headers=headers,
                    download_dir=download_dir,
                )
                text = _extract_pdf_text(pdf_path)
            except UnsupportedGoogleDriveFile as exc:
                skipped.append(
                    {
                        "file_id": file_id,
                        "name": name,
                        "mime_type": mime_type,
                        "reason": str(exc),
                    }
                )
                logger.info("파일 '%s'은(는) 지원하지 않는 형식입니다: %s", name, exc)
                continue
            except GoogleDriveAPIError as exc:
                skipped.append(
                    {
                        "file_id": file_id,
                        "name": name,
                        "mime_type": mime_type,
                        "reason": f"API 오류: {exc}",
                    }
                )
                logger.warning("파일 '%s' 처리 중 API 오류: %s", name, exc)
                continue

            converted.append(
                GoogleDriveFile(
                    file_id=file_id,
                    name=name,
                    mime_type=mime_type,
                    modified_time=file.get("modifiedTime", ""),
                    web_view_link=file.get("webViewLink"),
                    text=text,
                    format=fmt,
                    pdf_path=pdf_path,
                )
            )
            logger.info("파일 '%s' 동기화 완료", name)

    return converted, skipped
