import os
import io
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from googleapiclient.errors import HttpError
from pathlib import Path
import time
from dotenv import load_dotenv  

load_dotenv()

SCOPES = ['https://www.googleapis.com/auth/drive']
TOKEN_FILE = 'token.json'

CONVERTIBLE_MIME_TYPES = [
    'application/vnd.google-apps.document',
    'application/vnd.google-apps.spreadsheet',
    'application/vnd.google-apps.presentation',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document', # docx
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', # xlsx
    'application/vnd.openxmlformats-officedocument.presentationml.presentation' # pptx
]

def authenticate():
    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            client_id = os.getenv("GOOGLE_CLIENT_ID")
            client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
            project_id = os.getenv("GOOGLE_PROJECT_ID")
            auth_uri = os.getenv("GOOGLE_AUTH_URI")
            token_uri = os.getenv("GOOGLE_TOKEN_URI")

            # .env 파일에 값이 제대로 설정되었는지 확인
            if not client_id or not client_secret:
                print("[오류] .env 파일에 GOOGLE_CLIENT_ID와 GOOGLE_CLIENT_SECRET이 없습니다.")
                print(".env 파일을 확인하고 스크립트를 다시 시작하세요.")
                return None

            # 2. credentials.json 파일 대신, 환경 변수로 client_config 딕셔너리를 만듦
            client_config = {
                "installed": {
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "project_id": project_id,
                    "auth_uri": auth_uri,
                    "token_uri": token_uri,
                    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                    "redirect_uris": ["http://localhost"]
                }
            }
            
            flow = InstalledAppFlow.from_client_config(
                client_config, SCOPES)
            creds = flow.run_local_server(port=0)

        with open(TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())
    
    try:
        service = build('drive', 'v3', credentials=creds)
        print("구글 드라이브 인증 성공")
        return service
    except HttpError as error:
        print(f"서비스 생성 중 오류 발생: {error}")
        return None

def get_all_convertible_files(service):
    
    # 내 드라이브에만 있는 (소유자가 'me'인) 파일만 가져옵니다.
    
    all_files = []
    page_token = None
    
    # 1. 변환 가능한 파일 형식 지정
    query = "(" + " or ".join(f"mimeType = '{mime}'" for mime in CONVERTIBLE_MIME_TYPES) + ")"
    # 2. 휴지통에 없는 파일
    query += " and trashed=false"
    # 3. 소유자(owners)가 나인 파일만 검색
    query += " and 'me' in owners"
    
    print(f"내 드라이브에서 변환 가능한 모든 문서를 검색합니다...")
    
    try:
        while True:
            response = service.files().list(
                q=query,
                corpora='user', 
                fields='nextPageToken, files(id, name, mimeType, driveId)', # driveId도 만약을 위해 계속 확인
                pageToken=page_token
            ).execute()
            
            files = response.get('files', [])
            
            for f in files:
                if not f.get('driveId'): # driveId가 없는(None) 파일만 추가
                    all_files.append(f)
                else:
                    print(f"   (필터링: 공유 드라이브 파일 '{f.get('name')}' 제외)")
            

            page_token = response.get('nextPageToken', None)
            if page_token is None:
                break
            
            print(f"   파일 {len(all_files)}개 발견... 다음 페이지 검색 중...")

        print(f" 총 {len(all_files)}개의 변환 대상 문서를 찾았습니다.")
        return all_files

    except HttpError as error:
        print(f" 파일 목록 검색 중 API 오류 발생: {error}")
        return []

def convert_file_to_pdf(service, file_to_convert):
    # 파일 1개를 PDF로 변환 
    file_id = file_to_convert.get('id')
    file_name = file_to_convert.get('name')
    mime_type = file_to_convert.get('mimeType')
    
    print(f"\n--- 🔄 '{file_name}' 변환 시작 ---")
    
    temporary_google_doc_id = None 
    file_id_to_export = None
    
    try:
        if 'google-apps' in mime_type:
            file_id_to_export = file_id
        
        elif 'openxmlformats-officedocument' in mime_type:
            print(f"   (파일이 '{mime_type}'입니다. Google 문서로 임시 변환합니다...)")
            
            if 'wordprocessingml' in mime_type:
                target_mime_type = 'application/vnd.google-apps.document'
            else:
                target_mime_type = 'application/vnd.google-apps.spreadsheet'

            copy_metadata = {'name': f"[임시 변환] {file_name}", 'mimeType': target_mime_type}
            copy_metadata['parents'] = ['root'] 
            
            temp_file = service.files().copy(fileId=file_id, body=copy_metadata).execute()
            
            temporary_google_doc_id = temp_file.get('id')
            file_id_to_export = temporary_google_doc_id
            
            print(f"   (임시 'Google 문서' 생성 완료. ID: {temporary_google_doc_id})")
        
        else:
            # 지원하지 않는 파일 형식 
            return False

        print("   PDF로 변환을 요청합니다 ")
        request = service.files().export_media(
            fileId=file_id_to_export,
            mimeType='application/pdf'
        )
        
        output_filename = f"{Path(file_name).stem}.pdf"
        fh = io.FileIO(output_filename, 'wb')
        downloader = MediaIoBaseDownload(fh, request)
        
        done = False
        while done is False:
            status, done = downloader.next_chunk()
            print(f"   다운로드 진행 중... {int(status.progress() * 100)}%")

        print(f"   -> 다운로드 성공! {output_filename} 이름으로 PDF가 저장되었습니다.")
        return True

    except HttpError as error:
        print(f"'{file_name}' 변환 중 API 오류 발생: {error}")
        return False
    
    finally:
        if temporary_google_doc_id:
            try:
                print(f"   (임시 파일(ID: {temporary_google_doc_id})을 삭제합니다...)")
                service.files().delete(fileId=temporary_google_doc_id).execute()
            except HttpError as error:
                print(f"   임시 파일 삭제 중 오류 발생: {error}")

# 메인 
if __name__ == '__main__':
    # token.json이 없거나 만료되었을 때만 인증을 시도
    if not os.path.exists(TOKEN_FILE):
         print(f"사용자를 찾을 수 없습니다. 새 인증을 시작합니다.")

    service = authenticate() 
    if service:
        files_to_process = get_all_convertible_files(service)
        
        if not files_to_process:
            print("\n변환할 문서가 드라이브에 없습니다.")
        else:
            print(f"\n--- 총 {len(files_to_process)}개의 문서 변환을 시작합니다. ---")
            
            success_count = 0
            fail_count = 0
            
            for i, file in enumerate(files_to_process):
                print(f"\n--- 작업 ({i+1}/{len(files_to_process)}) ---")
                if convert_file_to_pdf(service, file):
                    success_count += 1
                else:
                    fail_count += 1
                
                print("   (API 제한을 피하기 위해 2초 대기...)")
                time.sleep(2) 
            
            print(f"\n--- 모든 작업 완료! ---")
            print(f"  성공: {success_count}개")
            print(f"  실패: {fail_count}개")