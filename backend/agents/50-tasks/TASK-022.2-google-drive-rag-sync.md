---
id: TASK-0022.2
type: task
title: Google Drive 파일 RAG 동기화 API 구현
description: "Google Drive에서 승인된 파일을 워크스페이스 RAG 스토리지로 동기화하는 백엔드 파이프라인을 구축한다."
status: done
owner: backend
updated: 2025-10-30
---

## 요청 사항
- Google Drive API에서 사용자가 다운로드할 수 있는 파일만 선별하고 미지원 형식(HWP, PDF 등)을 제외해야 한다.
- 문서/스프레드시트/프레젠테이션 등 Google Workspace 형식은 Export API를 통해 텍스트 기반으로 변환한다.
- 변환된 텍스트를 청크로 분할해 LangChain `Document`로 구성하고, 기본 RAG 인덱스(`DEFAULT_RAG_INDEX_NAME`)를 갱신한다.
- 동기화 결과와 스킵된 파일 목록, JSONL 레코드를 API 응답에 포함해 진단이 가능하도록 한다.

## 진행 기록
- 2025-10-29: `fetch_authorized_text_files` 모듈을 추가해 Google Drive 파일 목록/다운로드/형식 변환 로직을 정리했다.
- 2025-10-29: `build_records_from_files`와 `build_documents_from_records`로 청크 분할 및 메타데이터 주입을 표준화했다.
- 2025-10-30: `/google-drive/files/pull` 라우터가 토큰 갱신, 파일 변환, 크로마 벡터 스토어 갱신, 데이터 소스/인덱스 메타데이터 업데이트를 한 번에 수행하도록 구현했다.

## 결과
- Google Drive에서 HWP를 제외한 텍스트 기반 파일이 워크스페이스 RAG에 적재되며, `ChromaRAGService.replace_documents` 호출로 인덱스가 최신 상태를 유지한다.
- 응답 본문에 변환된 파일 정보, JSONL 레코드, 스킵된 파일 이유가 포함되어 재동기화 및 오류 분석이 용이하다.
- 데이터 소스 `synced` 타임스탬프와 `RagIndex` 메타데이터가 갱신되어 대시보드에 최신 동기화 현황이 반영된다.
