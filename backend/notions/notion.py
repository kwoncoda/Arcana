"""
Notion OAuth + FastAPI 최소 예제
- /login: Notion 동의 화면으로 리다이렉트
- /oauth/callback: code→access_token 교환 후 저장
- /me/pages: 로그인(설치)된 워크스페이스 기준 모든 접근 가능한 페이지 메타데이터 수집(페이징)
- /me/pages?full=true: 각 페이지의 블록 콘텐츠까지 재귀적으로 수집 (부하 큼, limit 권장)
- /me/pages/{page_id}/content: 특정 페이지 콘텐츠 트리만 조회

[사전 준비]
1) Notion Developers에서 Public Integration 생성
   - Redirect URI: 예) http://localhost:8000/oauth/callback
   - Capabilities: 필요한 읽기 권한(Read content) 등만 최소 요청
2) .env 파일 생성 (앱 루트)
   NOTION_CLIENT_ID=xxx
   NOTION_CLIENT_SECRET=xxx
   NOTION_REDIRECT_URI=http://localhost:8000/oauth/callback

[실행]
uv add fastapi uvicorn python-dotenv notion-client httpx sqlalchemy
uv run uvicorn app:app --reload --port 8000

그 후 http://localhost:8000/login 접속 → 동의 → /oauth/callback → 토큰 저장
응답 body의 workspace_id를 기록해 두세요. 이후 요청 헤더 X-Workspace-Id 또는 쿼리 ?workspace_id= 로 지정.
"""

from __future__ import annotations

import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import httpx
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from notion_client import Client
from notion_client.errors import APIResponseError
from pydantic import BaseModel
from sqlalchemy import Column, DateTime, String, create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

# -----------------------
# 환경 변수 로드
# -----------------------
load_dotenv()
CLIENT_ID = os.getenv("NOTION_CLIENT_ID")
CLIENT_SECRET = os.getenv("NOTION_CLIENT_SECRET")
REDIRECT_URI = os.getenv("NOTION_REDIRECT_URI")

if not CLIENT_ID or not CLIENT_SECRET or not REDIRECT_URI:
    raise RuntimeError(".env에 NOTION_CLIENT_ID/NOTION_CLIENT_SECRET/NOTION_REDIRECT_URI를 설정하세요.")

NOTION_AUTH_URL = "https://api.notion.com/v1/oauth/authorize"
NOTION_TOKEN_URL = "https://api.notion.com/v1/oauth/token"

# -----------------------
# FastAPI 앱
# -----------------------
app = FastAPI(title="Notion OAuth Starter", version="1.0.0")

# -----------------------
# 상태(state) 저장 (간단히 메모리)
# 실제 운영에서는 Redis 등 외부 스토리지 사용 권장
# -----------------------
_state_store: dict[str, datetime] = {}
STATE_TTL = timedelta(minutes=10)

# -----------------------
# DB 설정 (SQLite + SQLAlchemy)
# -----------------------
engine = create_engine("sqlite:///notion_tokens.db", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, autoflush=False, autocommit=False)
Base = declarative_base()


class NotionToken(Base):
    __tablename__ = "notion_tokens"
    # 워크스페이스 단위로 저장 (동일 워크스페이스에 앱이 설치되면 고유 ID)
    workspace_id = Column(String, primary_key=True)
    bot_id = Column(String, nullable=False)
    access_token = Column(String, nullable=False)
    refresh_token = Column(String, nullable=True)
    token_type = Column(String, nullable=True)  # 보통 "bearer"
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))


Base.metadata.create_all(bind=engine)


# -----------------------
# 유틸: DB 세션 의존성
# -----------------------

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


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
    # owner=user 로 사용자/워크스페이스 설치 허용
    # response_type=code, client_id, redirect_uri, state
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
# OAuth: refresh_token → 새 access_token
# -----------------------
async def refresh_access_token(db: Session, workspace_id: str) -> NotionToken:
    token_row = db.get(NotionToken, workspace_id)
    if not token_row or not token_row.refresh_token:
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

    token_row.access_token = data.get("access_token") or token_row.access_token
    token_row.refresh_token = data.get("refresh_token") or token_row.refresh_token
    token_row.token_type = data.get("token_type") or token_row.token_type
    token_row.updated_at = datetime.now(timezone.utc)
    db.add(token_row)
    db.commit()
    return token_row


# -----------------------
# 저장/조회 유틸
# -----------------------

def upsert_tokens(db: Session, data: Dict[str, Any]) -> NotionToken:
    workspace_id = data.get("workspace_id")
    bot_id = data.get("bot_id")
    access_token = data.get("access_token")
    refresh_token = data.get("refresh_token")
    token_type = data.get("token_type")

    if not (workspace_id and bot_id and access_token):
        raise HTTPException(status_code=500, detail="Notion 토큰 응답이 예상과 다릅니다.")

    row = db.get(NotionToken, workspace_id)
    if not row:
        row = NotionToken(
            workspace_id=workspace_id,
            bot_id=bot_id,
            access_token=access_token,
            refresh_token=refresh_token,
            token_type=token_type,
            updated_at=datetime.now(timezone.utc),
        )
    else:
        row.bot_id = bot_id
        row.access_token = access_token
        row.refresh_token = refresh_token or row.refresh_token
        row.token_type = token_type or row.token_type
        row.updated_at = datetime.now(timezone.utc)

    db.add(row)
    db.commit()
    return row


def get_token_row(db: Session, workspace_id: str) -> NotionToken:
    row = db.get(NotionToken, workspace_id)
    if not row:
        raise HTTPException(status_code=404, detail="해당 workspace_id의 토큰이 없습니다. /login으로 설치/동의하세요.")
    return row


# -----------------------
# Notion 클라이언트 팩토리 (401 → 자동 리프레시 1회 재시도)
# -----------------------
async def get_notion_client(db: Session, workspace_id: str) -> Client:
    row = get_token_row(db, workspace_id)
    return Client(auth=row.access_token)


async def notion_call_with_refresh(db: Session, workspace_id: str, func, *args, **kwargs):
    client = await get_notion_client(db, workspace_id)
    try:
        return func(client, *args, **kwargs)
    except APIResponseError as e:
        # 401 Unauthorized 시 리프레시 후 1회 재시도
        if getattr(e, "status", None) == 401:
            await refresh_access_token(db, workspace_id)
            client = await get_notion_client(db, workspace_id)
            return func(client, *args, **kwargs)
        raise


# -----------------------
# 페이지 제목 추출 유틸 (DB 항목/일반 페이지 모두 커버 시도)
# -----------------------

def extract_page_title(page: Dict[str, Any]) -> str:
    # DB 아이템의 경우 title 속성이 properties에 존재
    props = page.get("properties", {}) or {}
    for key, val in props.items():
        if val and val.get("type") == "title":
            rich = val.get("title") or []
            texts = [t.get("plain_text", "") for t in rich]
            title = "".join(texts).strip()
            if title:
                return title
    # 일반 페이지는 title을 별도로 가져오기가 어려울 수 있어 URL fallback
    return page.get("url") or page.get("id")


# -----------------------
# 블록 콘텐츠 재귀 수집
# -----------------------

def serialize_block(block: Dict[str, Any]) -> Dict[str, Any]:
    # 핵심 필드만 보존 (원하면 확장)
    btype = block.get("type")
    payload = {
        "id": block.get("id"),
        "type": btype,
        "has_children": block.get("has_children", False),
        "created_time": block.get("created_time"),
        "last_edited_time": block.get("last_edited_time"),
        "data": block.get(btype, {}),
    }
    return payload


def list_block_children_all(client: Client, block_id: str) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    start_cursor: Optional[str] = None
    while True:
        res = client.blocks.children.list(block_id=block_id, start_cursor=start_cursor, page_size=100)
        batch = res.get("results", [])
        results.extend(batch)
        if not res.get("has_more"):
            break
        start_cursor = res.get("next_cursor")
    return results


def build_block_tree(client: Client, block_id: str) -> List[Dict[str, Any]]:
    tree: List[Dict[str, Any]] = []
    for blk in list_block_children_all(client, block_id):
        node = serialize_block(blk)
        if node.get("has_children"):
            node["children"] = build_block_tree(client, blk["id"])  # 재귀
        tree.append(node)
    return tree


# -----------------------
# 라우트: OAuth 시작
# -----------------------
@app.get("/login")
async def login():
    # CSRF 방지를 위해 state 사용
    state = secrets.token_urlsafe(24)
    _state_store[state] = datetime.now(timezone.utc)
    url = build_authorize_url(state)
    return RedirectResponse(url)


# -----------------------
# 라우트: OAuth 콜백
# -----------------------
@app.get("/oauth/callback")
async def oauth_callback(code: Optional[str] = None, state: Optional[str] = None, db: Session = Depends(get_db)):
    if not code or not state:
        raise HTTPException(status_code=400, detail="code/state 누락")

    # state 검증 및 만료 확인
    ts = _state_store.pop(state, None)
    if not ts or datetime.now(timezone.utc) - ts > STATE_TTL:
        raise HTTPException(status_code=400, detail="state 검증 실패 또는 만료")

    data = await exchange_code_for_tokens(code)
    row = upsert_tokens(db, data)

    return {
        "message": "Notion 통합 설치/인증 완료",
        "workspace_id": row.workspace_id,
        "bot_id": row.bot_id,
        "token_type": row.token_type,
        "updated_at": row.updated_at.isoformat(),
    }


# -----------------------
# 라우트: 사용자 페이지 목록(메타)
# -----------------------
class PagesResponse(BaseModel):
    total: int
    pages: List[Dict[str, Any]]


@app.get("/me/pages", response_model=PagesResponse)
async def list_my_pages(
    full: bool = Query(False, description="True면 각 페이지의 콘텐츠 트리까지 포함(부하 큼)"),
    limit: Optional[int] = Query(None, ge=1, le=1000, description="가져올 최대 페이지 수(없으면 모두)"),
    workspace_id: str = Depends(get_workspace_id_dep),
    db: Session = Depends(get_db),
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
        # 각 페이지의 블록 트리를 추가 (시간/요청량이 큼)
        def _attach_content(client: Client, pages: List[Dict[str, Any]]):
            enriched = []
            for p in pages:
                try:
                    content = build_block_tree(client, p["id"])  # 재귀 수집
                except APIResponseError as e:
                    # 권한/삭제 등으로 실패할 수 있으니 건너뜀
                    content = {"error": str(e)}
                enriched.append({**p, "content": content})
            return enriched

        pages = await notion_call_with_refresh(db, workspace_id, _attach_content, pages)

    return {"total": len(pages), "pages": pages}


# -----------------------
# 라우트: 특정 페이지 콘텐츠만 (개별 트리)
# -----------------------
@app.get("/me/pages/{page_id}/content")
async def get_page_content(page_id: str, workspace_id: str = Depends(get_workspace_id_dep), db: Session = Depends(get_db)):
    def _get_content(client: Client, pid: str):
        return build_block_tree(client, pid)

    content = await notion_call_with_refresh(db, workspace_id, _get_content, page_id)
    return {"page_id": page_id, "content": content}


# -----------------------
# 라우트: 토큰 강제 리프레시 (테스트용)
# -----------------------
@app.post("/me/token/refresh")
async def api_refresh_token(workspace_id: str = Depends(get_workspace_id_dep), db: Session = Depends(get_db)):
    row = await refresh_access_token(db, workspace_id)
    return {
        "workspace_id": row.workspace_id,
        "updated_at": row.updated_at.isoformat(),
    }
