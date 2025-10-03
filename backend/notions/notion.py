"""Notion OAuth + FastAPI 라우트/유틸 (DB: notion_oauth_credentials 스키마 준수)"""

from __future__ import annotations

import os
import secrets
import json
import base64
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import httpx
from fastapi import HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from notion_client import Client
from notion_client.errors import APIResponseError
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session
from utils.db import Base
from models import NotionOauthCredentials, DataSource

# -----------------------
# 환경 변수 로드
# -----------------------
CLIENT_ID = os.getenv("NOTION_CLIENT_ID")
CLIENT_SECRET = os.getenv("NOTION_CLIENT_SECRET")
REDIRECT_URI = os.getenv("NOTION_REDIRECT_URI")

if not CLIENT_ID or not CLIENT_SECRET or not REDIRECT_URI:
    raise RuntimeError(".env에 NOTION_CLIENT_ID/NOTION_CLIENT_SECRET/NOTION_REDIRECT_URI를 설정하세요.")

NOTION_AUTH_URL = "https://api.notion.com/v1/oauth/authorize"
NOTION_TOKEN_URL = "https://api.notion.com/v1/oauth/token"

# -----------------------
# 상태(state) 저장
# -----------------------
_state_store: dict[str, datetime] = {}
STATE_TTL = timedelta(minutes=10)

def _b64url_encode(d: dict) -> str:
    raw = json.dumps(d, separators=(",", ":"), ensure_ascii=False).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")

def _b64url_decode(s: str) -> dict:
    pad = "=" * (-len(s) % 4)
    raw = base64.urlsafe_b64decode(s + pad)
    return json.loads(raw)


# -----------------------
# 유틸: Workspace ID 추출 (헤더 또는 쿼리)
# -----------------------
def get_workspace_id_dep(request: Request, workspace_id: Optional[str] = Query(None)) -> str:
    ws = request.headers.get("X-Workspace-Id") or workspace_id
    if not ws:
        raise HTTPException(status_code=400, detail="workspace_id가 필요합니다. X-Workspace-Id 헤더 또는 ?workspace_id= 로 전달하세요.")
    return ws

# -----------------------
# OAuth: authorize URL 생성
# -----------------------
def build_authorize_url(state: str) -> str:
    from urllib.parse import urlencode
    query = urlencode(
        {
            "owner": "user",
            "client_id": CLIENT_ID,
            "redirect_uri": REDIRECT_URI,
            "response_type": "code",
            "state": state,
        }
    )
    return f"{NOTION_AUTH_URL}?{query}"

# -----------------------
# OAuth: code → token 교환
# -----------------------
async def exchange_code_for_tokens(code: str) -> Dict[str, Any]:
    auth = httpx.BasicAuth(CLIENT_ID, CLIENT_SECRET)
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            NOTION_TOKEN_URL,
            auth=auth,
            json={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": REDIRECT_URI,
            },
        )
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    return resp.json()

# -----------------------
# 저장/조회 유틸
# -----------------------
def upsert_tokens(
    db: Session,
    data: Dict[str, Any],
    *,
    user_idx: int,
    data_source_idx: int,
) -> NotionOauthCredentials:
    """
    Notion 응답(JSON)을 받아 notion_oauth_credentials에 upsert.
    고유성 기준: UNIQUE(provider, bot_id)
    """
    provider = "notion"
    workspace_id = data.get("workspace_id")  # Notion 워크스페이스 ID
    bot_id = data.get("bot_id")
    access_token = data.get("access_token")
    refresh_token = data.get("refresh_token")
    token_type = data.get("token_type", "bearer")
    workspace_name = data.get("workspace_name")
    workspace_icon = data.get("workspace_icon")
    expires_in = data.get("expires_in")  # 제공되면 초 단위

    if not (bot_id and access_token):
        raise HTTPException(status_code=500, detail="Notion 토큰 응답이 예상과 다릅니다.")

    row = db.scalar(
        select(NotionOauthCredentials).where(
            NotionOauthCredentials.provider == provider,
            NotionOauthCredentials.bot_id == bot_id,
        )
    )

    if not row:
        row = db.scalar(
            select(NotionOauthCredentials).where(
                NotionOauthCredentials.data_source_idx == data_source_idx,
                NotionOauthCredentials.user_idx == user_idx,
            )
        )

    now_utc = datetime.utcnow()
    expires_at = (now_utc + timedelta(seconds=int(expires_in))) if expires_in else None

    if not row:
        row = NotionOauthCredentials(
            user_idx=user_idx,
            data_source_idx=data_source_idx,
            provider=provider,
            bot_id=bot_id,
            provider_workspace_id=workspace_id,
            workspace_name=workspace_name,
            workspace_icon=workspace_icon,
            token_type=token_type,
            access_token=access_token,
            refresh_token=refresh_token,
            expires=expires_at,
            created=now_utc,
            updated=now_utc,
            provider_payload=data,
        )
    else:
        row.user_idx = user_idx
        row.data_source_idx = data_source_idx
        row.provider = provider
        row.bot_id = bot_id
        row.provider_workspace_id = workspace_id or row.provider_workspace_id
        row.workspace_name = workspace_name or row.workspace_name
        row.workspace_icon = workspace_icon or row.workspace_icon
        row.token_type = token_type or row.token_type
        row.access_token = access_token
        row.refresh_token = refresh_token or row.refresh_token
        row.expires = expires_at or row.expires
        row.updated = now_utc
        row.provider_payload = data

    db.add(row)
    data_source = db.scalar(select(DataSource).where(DataSource.idx == data_source_idx))
    if data_source:
        data_source.status = "connected"
        db.add(data_source)
    db.commit()
    db.refresh(row)
    return row

def get_token_row_by_provider_ws(db: Session, workspace_id: str) -> NotionOauthCredentials:
    row = db.scalar(
        select(NotionOauthCredentials).where(
            NotionOauthCredentials.provider == "notion",
            NotionOauthCredentials.provider_workspace_id == workspace_id,
        )
    )
    if not row:
        raise HTTPException(status_code=404, detail="해당 workspace_id의 자격증명이 없습니다. /login으로 설치/동의하세요.")
    return row

# -----------------------
# OAuth: refresh_token → 새 access_token
# -----------------------
async def refresh_access_token(db: Session, workspace_id: str) -> NotionOauthCredentials:
    token_row = get_token_row_by_provider_ws(db, workspace_id)
    if not token_row.refresh_token:
        raise HTTPException(status_code=401, detail="리프레시 토큰이 없습니다. 다시 /login 하세요.")

    auth = httpx.BasicAuth(CLIENT_ID, CLIENT_SECRET)
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            NOTION_TOKEN_URL,
            auth=auth,
            json={
                "grant_type": "refresh_token",
                "refresh_token": token_row.refresh_token,
            },
        )
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    data = resp.json()

    now_utc = datetime.utcnow()
    expires_in = data.get("expires_in")
    token_row.access_token = data.get("access_token") or token_row.access_token
    token_row.refresh_token = data.get("refresh_token") or token_row.refresh_token
    token_row.token_type = data.get("token_type") or token_row.token_type
    token_row.expires = (now_utc + timedelta(seconds=int(expires_in))) if expires_in else token_row.expires
    token_row.updated = now_utc

    db.add(token_row)
    db.commit()
    db.refresh(token_row)
    return token_row

# -----------------------
# Notion 클라이언트 (401 → 자동 리프레시 1회)
# -----------------------
async def get_notion_client(db: Session, workspace_id: str) -> Client:
    row = get_token_row_by_provider_ws(db, workspace_id)
    return Client(auth=row.access_token)

async def notion_call_with_refresh(db: Session, workspace_id: str, func, *args, **kwargs):
    client = await get_notion_client(db, workspace_id)
    try:
        return func(client, *args, **kwargs)
    except APIResponseError as e:
        if getattr(e, "status", None) == 401:
            await refresh_access_token(db, workspace_id)
            client = await get_notion_client(db, workspace_id)
            return func(client, *args, **kwargs)
        raise

# -----------------------
# 페이지 제목 추출
# -----------------------
def extract_page_title(page: Dict[str, Any]) -> str:
    props = page.get("properties", {}) or {}
    for _, val in props.items():
        if val and val.get("type") == "title":
            rich = val.get("title") or []
            texts = [t.get("plain_text", "") for t in rich]
            title = "".join(texts).strip()
            if title:
                return title
    return page.get("url") or page.get("id")

# -----------------------
# 블록 콘텐츠 재귀 수집
# -----------------------
def serialize_block(block: Dict[str, Any]) -> Dict[str, Any]:
    btype = block.get("type")
    return {
        "id": block.get("id"),
        "type": btype,
        "has_children": block.get("has_children", False),
        "created_time": block.get("created_time"),
        "last_edited_time": block.get("last_edited_time"),
        "data": block.get(btype, {}),
    }

def list_block_children_all(client: Client, block_id: str) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    start_cursor: Optional[str] = None
    while True:
        res = client.blocks.children.list(block_id=block_id, start_cursor=start_cursor, page_size=100)
        results.extend(res.get("results", []))
        if not res.get("has_more"):
            break
        start_cursor = res.get("next_cursor")
    return results

def build_block_tree(client: Client, block_id: str) -> List[Dict[str, Any]]:
    tree: List[Dict[str, Any]] = []
    for blk in list_block_children_all(client, block_id):
        node = serialize_block(blk)
        if node.get("has_children"):
            node["children"] = build_block_tree(client, blk["id"])
        tree.append(node)
    return tree

# -----------------------
# 라우트: OAuth 시작 (/login)
# -----------------------
async def login(user_idx: Optional[int] = None):
    """
    테스트/초기 버전: 쿼리로 user_idx를 받는다.
    예) /login?user_idx=1&data_source_idx=1
    """
    if user_idx is None or data_source_idx is None:
        raise HTTPException(status_code=400, detail="user_idx와 data_source_idx가 필요합니다. /login?user_idx=..&data_source_idx=..")

    nonce = secrets.token_urlsafe(16)
    _state_store[nonce] = datetime.now(timezone.utc)

    state_payload = {"nonce": nonce, "user_idx": user_idx, "data_source_idx": data_source_idx}
    state = _b64url_encode(state_payload)

    url = build_authorize_url(state)
    return RedirectResponse(url)

# -----------------------
# 라우트: OAuth 콜백 (/oauth/callback)
# -----------------------
async def oauth_callback(
    code: Optional[str],
    state: Optional[str],
    db: Session,
):
    if not code or not state:
        raise HTTPException(status_code=400, detail="code/state 누락")

    try:
        payload = _b64url_decode(state)
        nonce = payload.get("nonce")
    except Exception:
        raise HTTPException(status_code=400, detail="state 손상")

    ts = _state_store.pop(nonce, None)
    if not ts or datetime.now(timezone.utc) - ts > STATE_TTL:
        raise HTTPException(status_code=400, detail="state 검증 실패 또는 만료")

    user_idx = payload.get("user_idx")
    data_source_idx = payload.get("data_source_idx")
    if not user_idx or not data_source_idx:
        raise HTTPException(status_code=400, detail="state에 user_idx/data_source_idx가 없습니다.")

    data = await exchange_code_for_tokens(code)
    row = upsert_tokens(db, data, user_idx=user_idx, data_source_idx=data_source_idx)

    return {
        "message": "Notion 통합 설치/인증 완료",
        "provider_workspace_id": row.provider_workspace_id,
        "bot_id": row.bot_id,
        "token_type": row.token_type,
        "updated": row.updated.isoformat(),
    }

# -----------------------
# 라우트: 사용자 페이지 목록(메타)
# -----------------------
class PagesResponse(BaseModel):
    total: int
    pages: List[Dict[str, Any]]

async def list_my_pages(
    full: bool,
    limit: Optional[int],
    workspace_id: str,
    db: Session,
):
    def _search_pages(client: Client):
        pages: List[Dict[str, Any]] = []
        start_cursor: Optional[str] = None
        fetched = 0
        while True:
            res = client.search(
                filter={"property": "object", "value": "page"},
                sort={"direction": "descending", "timestamp": "last_edited_time"},
                start_cursor=start_cursor,
                page_size=100,
            )
            batch = res.get("results", [])
            for pg in batch:
                item = {
                    "id": pg.get("id"),
                    "title": extract_page_title(pg),
                    "url": pg.get("url"),
                    "created_time": pg.get("created_time"),
                    "last_edited_time": pg.get("last_edited_time"),
                    "archived": pg.get("archived", False),
                    "icon": pg.get("icon"),
                    "cover": pg.get("cover"),
                    "parent": pg.get("parent"),
                }
                pages.append(item)
                fetched += 1
                if limit and fetched >= limit:
                    return pages
            if not res.get("has_more"):
                break
            start_cursor = res.get("next_cursor")
        return pages

    pages: List[Dict[str, Any]] = await notion_call_with_refresh(db, workspace_id, _search_pages)

    if full:
        def _attach_content(client: Client, pages: List[Dict[str, Any]]):
            enriched = []
            for p in pages:
                try:
                    content = build_block_tree(client, p["id"])
                except APIResponseError as e:
                    content = {"error": str(e)}
                enriched.append({**p, "content": content})
            return enriched

        pages = await notion_call_with_refresh(db, workspace_id, _attach_content, pages)

    return {"total": len(pages), "pages": pages}

# -----------------------
# 라우트: 특정 페이지 콘텐츠
# -----------------------
async def get_page_content(page_id: str, workspace_id: str, db: Session):
    def _get_content(client: Client, pid: str):
        return build_block_tree(client, pid)
    content = await notion_call_with_refresh(db, workspace_id, _get_content, page_id)
    return {"page_id": page_id, "content": content}

# -----------------------
# 라우트: 토큰 강제 리프레시
# -----------------------
async def api_refresh_token(workspace_id: str, db: Session):
    row = await refresh_access_token(db, workspace_id)
    return {
        "provider_workspace_id": row.provider_workspace_id,
        "updated": row.updated.isoformat(),
    }