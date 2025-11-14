---
id: TASK-0022.3
type: task
title: Google Drive token.json 의존성 제거
description: "로컬 token.json 파일 대신 DB에 저장된 OAuth 자격증명을 사용하도록 정리"
status: done
owner: backend
updated: 2025-10-30
---

## 요청 사항
- Google Drive 통합 코드에서 token.json 파일을 생성/사용하는 로직을 모두 제거한다.
- 액세스 토큰과 리프레시 토큰은 DB에 저장된 `GoogleDriveOauthCredentials` 엔티티로부터 불러오도록 한다.
- 수동 스크립트(`googleDrive.py`)도 새로운 인증 흐름에 맞게 갱신하거나 대체한다.

## 진행 기록
- 2025-10-30: 요구사항 분석 및 관련 모듈(`google_drive/googleDrive.py`, `google_drive/auth.py`, `routers/google_drive.py`) 파악.
- 2025-10-30: `google_drive/googleDrive.py`를 DB 자격증명 기반으로 리팩터링하고 token.json 의존성을 제거.
- 2025-10-30: 수동 스크립트가 DB 토큰 자동 갱신(리프레시) 경로를 사용하도록 검증.

## 결과
- Google Drive 수동 스크립트가 token.json 없이 DB의 `GoogleDriveOauthCredentials`를 사용해 인증한다.
- 만료된 토큰은 `ensure_valid_access_token`을 통해 자동으로 갱신된다.
- token.json 파일 입출력 로직이 사라져 배포 환경에서 파일 의존성이 제거되었다.

