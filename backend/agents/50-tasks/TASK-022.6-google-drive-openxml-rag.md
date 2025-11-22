---
id: TASK-0022.6
type: task
title: Google Drive OpenXML 구조 텍스트 RAG 적재
description: "Google Drive Word 계열 문서를 OpenXML XML과 함께 RAG에 보존할 수 있도록 백엔드 파이프라인을 확장한다."
status: done
owner: backend
updated: 2025-11-13
---

## 요청 사항
- DOCX 및 Google Docs 문서 동기화 시 `word/document.xml`을 추출해 RAG 메타데이터에 포함한다.
- JSONL 레코드와 `/google-drive/files/pull` 응답에 저장 경로와 구조화 포맷 정보를 노출한다.
- 기존 PDF 기반 처리 흐름과 호환되도록 구현한다.

## 진행 기록
- 2025-11-13: Google Drive 동기화 모듈에 OpenXML 추출 유틸리티(`_extract_docx_xml`, `_xml_to_plain_text`)를 연결하고 `GoogleDriveFile` 모델을 확장했다.
- 2025-11-13: JSONL/Document 메타데이터에 `structured_text`, `structured_format`, `file_path` 필드를 추가했다.
- 2025-11-13: `/google-drive/files/pull` 응답에 OpenXML 관련 정보를 반환하도록 조정하고 스토리/태스크 문서를 갱신했다.

## 결과
- 동기화된 DOCX 문서는 XML 태그가 포함된 `structured_text` 메타데이터와 함께 RAG에 적재된다.
- RAG 검색 결과에서 `structured_format`과 `file_path`를 확인해 원문 서식을 재구성할 수 있다.
- 기존 PDF 파일 처리 로직은 영향 없이 유지된다.