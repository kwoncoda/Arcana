---
id: TASK-0022.1
type: task
title: 구글 드라이브 OAuth 연동 및 자격증명 저장
description: "데이터 소스 및 Google OAuth 토큰을 Arcana 백엔드에서 관리할 수 있도록 확장"
status: done
owner: backend
updated: 2025-10-30
---

## 요청 사항
- 구글 드라이브 OAuth 인증을 서비스에 정식으로 통합해 테스트용 `token.json` 파일 없이 동작하도록 한다.
- `data_sources` 테이블에 `googledrive` 타입을 추가하고, 별도 자격증명 테이블을 생성한다.
- FastAPI에서 구글 드라이브 연동을 위한 연결/콜백 엔드포인트를 제공한다.

## 진행 기록
- 2025-10-30: Google Drive OAuth 전용 모델(`GoogleDriveOauthCredentials`)과 스키마를 설계하고 `init.sql`을 갱신했다.
- 2025-10-30: `/google-drive/connect` 및 `/google-drive/oauth/callback` 라우터를 추가해 OAuth 플로우를 구현했다.
- 2025-10-30: 구글 토큰 교환/사용자 정보 조회를 위한 헬퍼 모듈을 작성하고 데이터 소스 상태 업데이트 로직을 연결했다.

## 결과
- Google Drive 연동 시 데이터 소스와 자격증명이 DB에 저장되며, 성공 후 대시보드로 리디렉션된다.
- 사용자 외부 도구 현황 API에서 `googledrive` 데이터 소스가 정상적으로 노출된다.
