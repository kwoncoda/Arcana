import pandas as pd
import docx
import io
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from pathlib import Path

# --- 설정 ---
BASE_DIR = Path(__file__).resolve().parent
app = FastAPI()

# --- 라우팅 (경로 설정) ---

# 1. 웹 UI 페이지 제공
@app.get("/")
async def serve_html_page():
    return FileResponse(BASE_DIR / "local__host.html")

# 2. 파일 변환 API
@app.post("/convert-to-json/")
async def convert_file_to_json(file: UploadFile = File(...)):
    try:
        filename = file.filename
        
        # 확장자에 따라 분기
        if filename.endswith('.csv'):
            df = pd.read_csv(file.file)
            content = df.to_dict(orient='records')
            file_type = "csv"
            
        elif filename.endswith('.xlsx'):
            df = pd.read_excel(file.file, engine='openpyxl')
            content = df.to_dict(orient='records')
            file_type = "excel"

        elif filename.endswith('.docx'):
            file_content = await file.read()
            file_stream = io.BytesIO(file_content)
            document = docx.Document(file_stream)
            content = "\n".join([para.text for para in document.paragraphs])
            file_type = "docx"
            
        else:
            raise HTTPException(status_code=400, detail="Unsupported file format.")

    except Exception as e:
        # 파일 처리 중 어떤 오류든 발생하면 500 에러를 보냄
        raise HTTPException(status_code=500, detail=str(e))

    return {
        "filename": filename,
        "file_type": file_type,
        "content": content
    }