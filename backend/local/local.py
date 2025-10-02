import docx  # Word(.docx) 파일을 읽고 분석하는 라이브러리
import io    # 메모리 상에서 파일을 다루기 위한 라이브러리 (파일 호환성 문제 해결용)
from fastapi import FastAPI, UploadFile, File, HTTPException  
from fastapi.responses import FileResponse  
from pathlib import Path  # 운영체제에 상관없이 파일 경로를 다루기 위한 도구


# 현재 이 파이썬 파일(local.py)이 위치한 폴더의 절대 경로를 계산
BASE_DIR = Path(__file__).resolve().parent
app = FastAPI()


@app.get("/")
async def serve_html_page():
    return FileResponse(BASE_DIR / "local__host.html")

# 업로드된 파일을 받아 내용을 추출하고 JSON 형식으로 변환하여 반환
@app.post("/convert-to-json/")
async def convert_file_to_json(file: UploadFile = File(...)):
    
    # 파일 처리 로직
    try:
        # 업로드된 파일의 원래 이름
        filename = file.filename
        
        # 변환된 내용을 저장할 변수들을 초기화
        content = None
        file_type = ""
        
        # 파일 이름의 끝부분(확장자)을 확인하여 어떤 종류의 파일인지 판단
        if filename.endswith('.docx'):
            # 파일 종류를 docx로 기록
            file_type = "docx"
            
            #.docx 파일 처리
            # 1. 업로드된 파일의 모든 내용을 바이트(bytes) 형태로 메모리에 한번에 읽음
            file_content = await file.read()
            # 2. 읽어들인 바이트 데이터를 메모리 상의 가상 파일로 만듦 -> 호환성 문제 해결
            file_stream = io.BytesIO(file_content)
            # 3. 가상 파일을 읽어서 문서 객체를 생성
            document = docx.Document(file_stream)
            # 4. 문서 안의 모든 문단(paragraph)을 하나씩 순회하며 텍스트만 추출
            content = "\n".join([para.text for para in document.paragraphs])
            
        elif filename.endswith('.txt'):
            # 파일 종류를 txt로 기록합
            file_type = "txt"
            
            #.txt 파일 처리
            # 1. 업로드된 파일의 모든 내용을 바이트(bytes) 형태로 읽음
            file_content_bytes = await file.read()
            
            # 2. 바이트를 문자열로 변환 -> 한글 깨짐 방지를 위해 여러 인코딩을 시도
            try:
                # 2-1. 가장 표준적인 utf-8 방식으로 먼저 시도
                content = file_content_bytes.decode('utf-8')
            except UnicodeDecodeError:
                # 2-2. utf-8 실패 시 윈도우 한글 환경에서 자주 사용되는 cp949로 다시 시도
                content = file_content_bytes.decode('cp949', errors='ignore')
        else:
            # 지원하는 확장자가 아닐 경우 400번 에러 발생
            raise HTTPException(status_code=400, detail="Unsupported file format. Please upload a .docx file.")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    # --- 4. 성공적인 결과 반환 ---
    # JSON 형식의 문자열로 변환하여 사용자에게 응답합니다.
    return {
        "filename": filename,
        "file_type": file_type,
        "content": content
    }

