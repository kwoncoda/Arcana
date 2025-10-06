import logging

from fastapi import FastAPI

from routers import aiagent, notion, users

from fastapi.middleware.cors import CORSMiddleware


logging.basicConfig(
    level=logging.DEBUG,                        
    format="%(asctime)s %(levelname)s %(name)s :: %(message)s",
    force=True,           # uvicorn 핸들러 삭제
)

logger = logging.getLogger("arcana")  

# logging.getLogger("httpx").setLevel(logging.WARNING)
# logging.getLogger("uvicorn.access").setLevel(logging.INFO)

# swagger 페이지 소개
SWAGGER_HEADERS = {
    "version": "1.0.0",
    "description": "## 관리페이지에 오신것을 환영합니다 \n - API를 사용해 데이터를 전송할 수 있습니다. \n - 무분별한 사용은 하지 말아주세요 \n - 관리자 번호: 010-1234-5678",
    "contact": {
        "name": "Arcana",
        "url": "https://arcana.example.com",
    },
}

# FastAPI 초기화
app = FastAPI(
    title="Arcana Backend API",
    **SWAGGER_HEADERS,
    root_path="/api"
)

app.include_router(users.router)
app.include_router(notion.router)
app.include_router(aiagent.router)

#api설정값
app.add_middleware(
    CORSMiddleware,
    # 허용 ip
    #allow_origins=origins,
    #일단 열어둠
    allow_origins=["*"],
    # 인증, 쿠키
    #allow_credentials=True,
    # 허용 메소드
    allow_methods=["*"],
    # 허용 헤더
    allow_headers=["*"],  
)


# 공공 API

# 헬스 체크
@app.get("/health")
def health():
    return {"status": "ok"}


