import pandas as pd
import docx
import io
import traceback
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
app = FastAPI()

@app.get("/")
async def serve_html_page():
    return FileResponse(BASE_DIR / "local__host.html")

@app.post("/convert-to-json/")
async def convert_file_to_json(file: UploadFile = File(...)):
    try:
        filename = file.filename
        content = None
        file_type = ""
        if filename.endswith('.docx'):
            file_type = "docx"
            file_content = await file.read()
            file_stream = io.BytesIO(file_content)
            document = docx.Document(file_stream)
            content = "\n".join([para.text for para in document.paragraphs])
            
        else:
            raise HTTPException(status_code=400, detail="Unsupported file format.")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {
        "filename": filename,
        "file_type": file_type,
        "content": content
    }