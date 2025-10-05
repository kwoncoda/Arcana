import logging  # 로깅 기능 사용을 위한 logging 모듈 임포트 주석

from fastapi import FastAPI

from routers import notion, users

from fastapi.middleware.cors import CORSMiddleware

# swagger 페이지 소개
logging.basicConfig(  # 애플리케이션 전역 로깅 설정을 구성하는 주석
    level=logging.DEBUG,  # 로깅 레벨을 DEBUG로 설정하여 상세 정보를 수집하는 주석
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",  # 로그 출력 형식을 지정하는 주석
)

logger = logging.getLogger("arcana")  # 애플리케이션 전반에서 사용할 기본 로거 객체 생성 주석

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


