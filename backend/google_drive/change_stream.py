"""Google Drive Changes API 통합 로직."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple

import httpx

from .files import (
    CONVERTIBLE_MIME_TYPES,
    FILES_ENDPOINT,
    GoogleDriveAPIError,
)

import logging


logger = logging.getLogger(__name__)

CHANGES_ENDPOINT = "https://www.googleapis.com/drive/v3/changes"
START_PAGE_TOKEN_ENDPOINT = f"{CHANGES_ENDPOINT}/startPageToken"

_CHANGE_FIELDS = (
    "nextPageToken,newStartPageToken,"
    "changes(fileId,removed,file("
    "id,name,mimeType,modifiedTime,md5Checksum,version,parents,"
    "webViewLink,trashed,capabilities/canDownload))"
)

_FOLDER_MIME_TYPE = "application/vnd.google-apps.folder"


@dataclass(slots=True)
class ChangeBatch:
    """Changes API 호출 결과를 구조화한 데이터 컨테이너."""

    to_index: List[Dict[str, Any]]
    to_remove: List[str]
    skipped: List[Dict[str, str]]
    new_start_page_token: str


async def get_start_page_token(access_token: str) -> str:
    """Google Drive Changes API용 startPageToken을 조회한다."""

    headers = {"Authorization": f"Bearer {access_token}"}
    params = {"supportsAllDrives": "false"}

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(
            START_PAGE_TOKEN_ENDPOINT, headers=headers, params=params
        )

    if response.status_code != 200:
        raise GoogleDriveAPIError(response.text)

    payload = response.json()
    token = payload.get("startPageToken")
    if not token:
        raise GoogleDriveAPIError("startPageToken을 가져오지 못했습니다.")
    return str(token)


async def list_workspace_files(
    access_token: str,
    *,
    root_id: str,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, str]]]:
    """워크스페이스 루트 이하의 변환 가능한 파일 목록을 반환한다."""

    headers = {"Authorization": f"Bearer {access_token}"}
    params = {
        "pageSize": 200,
        "fields": (
            "nextPageToken, files(id, name, mimeType, modifiedTime, md5Checksum,"
            " version, webViewLink, parents, capabilities/canDownload)"
        ),
        "supportsAllDrives": "false",
        "includeItemsFromAllDrives": "false",
        "orderBy": "modifiedTime desc",
        "q": None,
    }

    convertible: List[Dict[str, Any]] = []
    skipped: List[Dict[str, str]] = []
    queue: deque[str] = deque([root_id])
    visited: set[str] = set()

    async with httpx.AsyncClient(timeout=60) as client:
        while queue:
            folder_id = queue.popleft()
            if folder_id in visited:
                continue
            visited.add(folder_id)

            folder_query = _build_folder_query(folder_id)
            params["q"] = folder_query

            page_token: Optional[str] = None
            while True:
                if page_token:
                    params["pageToken"] = page_token
                else:
                    params.pop("pageToken", None)

                response = await client.get(
                    FILES_ENDPOINT, headers=headers, params=params
                )
                if response.status_code != 200:
                    raise GoogleDriveAPIError(response.text)

                payload = response.json()
                files = payload.get("files", [])
                for file in files:
                    mime_type = file.get("mimeType") or ""
                    file_id = file.get("id") or ""
                    if mime_type == _FOLDER_MIME_TYPE:
                        if file_id:
                            queue.append(file_id)
                        continue

                    if mime_type not in CONVERTIBLE_MIME_TYPES:
                        skipped.append(
                            {
                                "file_id": file_id,
                                "name": file.get("name") or "",
                                "mime_type": mime_type,
                                "reason": "지원하지 않는 형식입니다.",
                            }
                        )
                        continue

                    convertible.append(file)

                page_token = payload.get("nextPageToken")
                if not page_token:
                    break

    logger.info(
        "Google Drive 루트(%s) 이하에서 %d개의 변환 대상 파일을 찾았습니다.",
        root_id,
        len(convertible),
    )
    return convertible, skipped


async def collect_workspace_changes(
    access_token: str,
    *,
    page_token: str,
    root_id: str,
) -> ChangeBatch:
    """Changes API를 통해 증분 변경을 수집한다."""

    headers = {"Authorization": f"Bearer {access_token}"}

    to_index: Dict[str, Dict[str, Any]] = {}
    to_remove: set[str] = set()
    skipped: Dict[str, Dict[str, str]] = {}
    new_start_page_token = page_token

    parents_cache: Dict[str, bool] = {}

    async with httpx.AsyncClient(timeout=60) as client:
        next_token: Optional[str] = page_token
        while next_token:
            params = {
                "pageToken": next_token,
                "pageSize": 200,
                "fields": _CHANGE_FIELDS,
                "includeItemsFromAllDrives": "false",
                "supportsAllDrives": "false",
                "restrictToMyDrive": "true",
            }

            response = await client.get(CHANGES_ENDPOINT, headers=headers, params=params)
            if response.status_code != 200:
                raise GoogleDriveAPIError(response.text)

            payload = response.json()
            new_start_page_token = payload.get("newStartPageToken") or new_start_page_token

            for change in payload.get("changes", []):
                change_type = change.get("changeType")
                if change_type and change_type != "file":
                    continue

                file_id = change.get("fileId") or ""
                if not file_id:
                    continue

                if change.get("removed"):
                    _mark_removed(file_id, to_index, to_remove, skipped)
                    continue

                file = change.get("file") or {}
                if file.get("trashed"):
                    _mark_removed(file_id, to_index, to_remove, skipped)
                    continue

                mime_type = file.get("mimeType") or ""
                if mime_type == _FOLDER_MIME_TYPE:
                    continue

                if mime_type not in CONVERTIBLE_MIME_TYPES:
                    skipped[file_id] = {
                        "file_id": file_id,
                        "name": file.get("name") or "",
                        "mime_type": mime_type,
                        "reason": "지원하지 않는 형식입니다.",
                    }
                    to_index.pop(file_id, None)
                    to_remove.discard(file_id)
                    continue

                capabilities = file.get("capabilities") or {}
                if not capabilities.get("canDownload", True):
                    skipped[file_id] = {
                        "file_id": file_id,
                        "name": file.get("name") or "",
                        "mime_type": mime_type,
                        "reason": "다운로드 권한이 없습니다.",
                    }
                    to_index.pop(file_id, None)
                    to_remove.discard(file_id)
                    continue

                parents: Iterable[str] = file.get("parents") or []
                if parents and await _is_within_workspace(
                    client, headers, parents, root_id, parents_cache
                ):
                    to_remove.discard(file_id)
                    skipped.pop(file_id, None)
                    to_index[file_id] = file
                else:
                    _mark_removed(file_id, to_index, to_remove, skipped)

            next_token = payload.get("nextPageToken")

    return ChangeBatch(
        to_index=list(to_index.values()),
        to_remove=list(to_remove),
        skipped=list(skipped.values()),
        new_start_page_token=new_start_page_token,
    )


def _mark_removed(
    file_id: str,
    to_index: Dict[str, Dict[str, Any]],
    to_remove: set[str],
    skipped: Dict[str, Dict[str, str]],
) -> None:
    """변경된 파일을 제거 대상으로 표시한다."""

    if not file_id:
        return
    to_index.pop(file_id, None)
    skipped.pop(file_id, None)
    to_remove.add(file_id)


def _build_folder_query(folder_id: str) -> str:
    """폴더 내 모든 하위 항목을 검색하기 위한 쿼리를 생성한다."""

    convertible_query = " or ".join(
        f"mimeType = '{mime}'" for mime in sorted(CONVERTIBLE_MIME_TYPES)
    )
    return " and ".join(
        filter(
            None,
            [
                "trashed=false",
                "'me' in owners",
                f"(({convertible_query}) or mimeType = '{_FOLDER_MIME_TYPE}')",
                f"'{folder_id}' in parents",
            ],
        )
    )


async def _is_within_workspace(
    client: httpx.AsyncClient,
    headers: Dict[str, str],
    parents: Iterable[str],
    root_id: str,
    cache: Dict[str, bool],
) -> bool:
    """파일이 워크스페이스 루트 하위에 존재하는지 확인한다."""

    for parent_id in parents:
        if parent_id == root_id:
            return True
        if await _has_root_ancestor(client, headers, parent_id, root_id, cache, set()):
            return True
    return False


async def _has_root_ancestor(
    client: httpx.AsyncClient,
    headers: Dict[str, str],
    folder_id: str,
    root_id: str,
    cache: Dict[str, bool],
    visiting: set[str],
) -> bool:
    if folder_id == root_id:
        return True
    if folder_id in visiting:
        return False

    cached = cache.get(folder_id)
    if cached is not None:
        return cached

    visiting.add(folder_id)
    metadata = await _fetch_folder_metadata(client, headers, folder_id)
    parents = metadata.get("parents") or []

    # My Drive 루트는 API 상 고정 ID("root")와 실제 ID가 다를 수 있으며
    # 실제 루트 폴더는 부모가 없으므로 이 경우를 루트로 간주한다.
    if root_id == "root" and not parents:
        cache[folder_id] = True
        visiting.discard(folder_id)
        return True
    for parent in parents:
        if parent == root_id or await _has_root_ancestor(
            client, headers, parent, root_id, cache, visiting
        ):
            cache[folder_id] = True
            visiting.discard(folder_id)
            return True

    visiting.discard(folder_id)
    cache[folder_id] = False
    return False


async def _fetch_folder_metadata(
    client: httpx.AsyncClient,
    headers: Dict[str, str],
    folder_id: str,
) -> Dict[str, Any]:
    response = await client.get(
        f"{FILES_ENDPOINT}/{folder_id}",
        headers=headers,
        params={"fields": "id, parents"},
    )
    if response.status_code != 200:
        raise GoogleDriveAPIError(response.text)
    return response.json()

