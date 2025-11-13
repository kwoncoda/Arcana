import asyncio
import io
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload

from google_drive import (
    GoogleDriveCredentialError,
    ensure_valid_access_token,
    get_connected_user_credential,
)
from utils.db import SessionLocal

load_dotenv()

SCOPES = ['https://www.googleapis.com/auth/drive']

CONVERTIBLE_MIME_TYPES = [
    'application/vnd.google-apps.document',
    'application/vnd.google-apps.spreadsheet',
    'application/vnd.google-apps.presentation',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document', # docx
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', # xlsx
    'application/vnd.openxmlformats-officedocument.presentationml.presentation' # pptx
]

def _load_oauth_credential() -> Credentials:
    """DB에 저장된 OAuth 자격증명으로 Google API Credentials를 생성한다."""

    workspace_idx = int(os.getenv("GOOGLE_DRIVE_WORKSPACE_IDX"))
    user_idx = int(os.getenv("GOOGLE_DRIVE_USER_IDX"))

    session = SessionLocal()
    try:
        credential = get_connected_user_credential(
            session,
            workspace_idx=workspace_idx,
            user_idx=user_idx,
        )

        async def _ensure() -> None:
            await ensure_valid_access_token(session, credential)

        asyncio.run(_ensure())
        session.refresh(credential)

        client_id = os.getenv("GOOGLE_CLIENT_ID")
        client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
        token_uri = os.getenv("GOOGLE_TOKEN_URI")

        return Credentials(
            token=credential.access_token,
            refresh_token=credential.refresh_token,
            token_uri=token_uri,
            client_id=client_id,
            client_secret=client_secret,
            scopes=SCOPES,
        )
    except GoogleDriveCredentialError as error:
        session.rollback()
        raise RuntimeError(
            "Google Drive OAuth 자격증명을 찾을 수 없습니다. 백엔드 OAuth 연동을 먼저 수행하세요."
        ) from error
    finally:
        session.close()


def authenticate():
    creds = _load_oauth_credential()

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