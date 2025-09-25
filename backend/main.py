from typing import Optional

from fastapi import Depends, FastAPI, Query
from sqlalchemy.orm import Session

from routers import users, notion

from notions import (
    PagesResponse,
    api_refresh_token,
    get_page_content,
    get_workspace_id_dep,
    list_my_pages,
    login,
    oauth_callback,
)
from utils.db import get_db


# swagger 페이지 소개
SWAGGER_HEADERS = {
    "version": "1.0.0",
    "description": "## 관리페이지에 오신것을 환영합니다 \n - API를 사용해 데이터를 전송할 수 있습니다. \n - 무분별한 사용은 하지 말아주세요 \n - 관리자 번호: 010-1234-5678",
    "contact": {
        "name": "Arcana",
        "url": "https://arcana.example.com",
    },
}

# FastAPI 초기화(CORS,Lifespan)
app = FastAPI(
    title="SaladBot Recommendation API",
    **SWAGGER_HEADERS,
    root_path="/api"
)

app.include_router(users.router)
app.include_router(notion.router)


# 공공 API

# 헬스 체크
@app.get("/api/health")
def health():
    return {"status": "ok"}




# Notion 관련 엔드포인트


# @app.get("/notionaccess")
# async def login_route():
#     return await login()


# @app.get("/oauth/callback")
# async def oauth_callback_route(
#     code: Optional[str] = None,
#     state: Optional[str] = None,
#     db: Session = Depends(get_db),
# ):
#     return await oauth_callback(code, state, db)


# @app.get("/me/pages", response_model=PagesResponse)
# async def list_my_pages_route(
#     full: bool = Query(False, description="True면 각 페이지의 콘텐츠 트리까지 포함(부하 큼)"),
#     limit: Optional[int] = Query(None, ge=1, le=1000, description="가져올 최대 페이지 수(없으면 모두)"),
#     workspace_id: str = Depends(get_workspace_id_dep),
#     db: Session = Depends(get_db),
# ):
#     return await list_my_pages(full, limit, workspace_id, db)


# @app.get("/me/pages/{page_id}/content")
# async def get_page_content_route(
#     page_id: str,
#     workspace_id: str = Depends(get_workspace_id_dep),
#     db: Session = Depends(get_db),
# ):
#     return await get_page_content(page_id, workspace_id, db)


# @app.post("/me/token/refresh")
# async def api_refresh_token_route(
#     workspace_id: str = Depends(get_workspace_id_dep),
#     db: Session = Depends(get_db),
# ):
#     return await api_refresh_token(workspace_id, db)


