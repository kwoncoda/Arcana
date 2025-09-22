from fastapi import FastAPI, HTTPException, Depends, Request




# swagger 페이지 소개
SWAGGER_HEADERS = {                                                             
    "version": "1.0.0",                                                        
    "description": "## 관리페이지에 오신것을 환영합니다 \n - API를 사용해 데이터를 전송할 수 있습니다. \n - 무분별한 사용은 하지 말아주세요 \n - 관리자 번호: 010-1234-5678", 
    "contact": {                                                                  
       "name": "Arcana",                                                       
       "url": "https://arcana.example.com"                                 
    },
}

# FastAPI 초기화(CORS,Lifespan) 
app = FastAPI(                                                                  
    title="SaladBot Recommendation API",                                         
    **SWAGGER_HEADERS                                                           
)

# 헬스 체크
@app.get("/api/health")                                                          
def health():                                                                   
    return {"status": "ok"}                                                    