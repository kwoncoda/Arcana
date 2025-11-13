---
id: TASK-0022.4
type: task
title: Google Drive 파일 PDF 저장 및 RAG 텍스트 추출
description: "Google Drive에서 변환 가능한 파일을 워크스페이스에 PDF로 저장하고 텍스트를 추출해 RAG 파이프라인에 전달한다."
status: done
owner: backend
updated: 2025-10-30
---

## 요청 사항
- Google Drive API에서 다운로드 가능한 문서/스프레드시트/프레젠테이션을 탐색하고, 페이지네이션을 따라가며 전체 목록을 수집한다.
- Google Workspace 네이티브 파일은 Export API로, Office 문서는 Google 문서 사본을 생성한 뒤 PDF로 변환한다.
- 변환된 PDF는 워크스페이스 스토리지 `<workspace>/googledrive/pdf` 경로에 파일명 정규화 규칙을 적용해 저장한다.
- 저장된 PDF에서 텍스트를 추출하고, 청크 분할 후 JSONL 레코드 및 LangChain `Document` 메타데이터에 `pdf_path`를 포함한다.
- 처리 현황과 스킵된 파일, 텍스트 추출 실패 등을 로깅해 운영 가시성을 확보한다.

## 진행 기록
- 2025-10-29: `_list_files`를 구현해 변환 가능 MIME 타입만 포함하도록 Google Drive 검색 쿼리를 최적화했다.
- 2025-10-29: `_download_file_as_pdf`와 `_write_pdf` 로직을 작성해 임시 Google 사본 생성, PDF Export, 워크스페이스 저장을 마쳤다.
- 2025-10-30: `_extract_pdf_text`, `_chunk_text`, `build_records_from_files` 체인을 통해 PDF 텍스트 추출과 청크 메타데이터 구성을 자동화했다.
- 2025-10-30: `/google-drive/files/pull` 엔드포인트가 PDF 저장 경로, JSONL 레코드, 스킵 로그를 응답으로 반환하도록 연동했다.

## 결과
- 증분 동기화 호출 시 변환된 PDF가 워크스페이스 스토리지에 축적되고, 동일한 경로 정보가 RAG 메타데이터에 포함된다.
- `ChromaRAGService.replace_documents`를 통해 추출 텍스트가 기본 RAG 인덱스에 적재되며, 인덱스 통계가 최신 상태로 갱신된다.
- 스킵된 파일 리스트와 상세 이유가 API 응답과 로그에 남아 재시도 전략 수립과 오류 분석이 쉬워졌다.