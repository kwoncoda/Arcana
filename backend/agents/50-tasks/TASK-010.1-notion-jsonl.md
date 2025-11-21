---
id: TASK-010.1
type: task
title: Notion 페이지 전처리 JSONL 생성 유틸 구현
status: done
owner: backend
updated: 2025-10-07
---

## 요청 사항
- Notion 페이지 수집 데이터를 RAG 인덱싱에 활용하기 좋은 JSONL 포맷으로 전처리하는 유틸리티를 notions 모듈에 추가한다.
- 결과에는 워크스페이스 이름과 페이지 URL 등 메타데이터를 포함한다.
- 샘플 JSONL을 생성해 형식을 검증할 수 있도록 한다.

## 진행 기록
- 2025-10-07: 기존 Notion Pull 결과 구조 검토 및 전처리 요구사항 정리.
- 2025-10-07: `backend/notions/notionPreprocess.py` 모듈 추가 및 전처리 로직 구현.
- 2025-10-07: 샘플 데이터로 JSONL(`backend/notions/sample_pages.jsonl`) 생성 및 내용 확인.

## 결과
- Notion Pull 응답을 워크스페이스/페이지 메타데이터와 함께 블록 단위 JSONL 레코드로 변환하는 유틸 완성.
- 샘플 JSONL을 통해 레코드 구조와 URL 포함 여부를 검증.
