---
id: TASK-0013.5
type: task
title: Notion RAG 청크 오버랩 비율 환경변수화
status: done
owner: backend
updated: 2025-10-10
---

## 1. 배경
- 노션 페이지를 RAG 인덱스에 적재할 때 인접 청크 사이 문맥이 끊기는 문제가 발생했다.
- 이전 구현은 고정 길이 오버랩에 의존하거나, 인입 데이터가 별도로 overlap을 지정하지 않으면 문장 경계가 손상됐다.
- 제품 요구사항은 기본적으로 청크 길이의 **10%**를 겹치되, 운영 환경에 따라 손쉽게 비율을 조정할 수 있어야 한다.

## 2. 목표
- 환경 변수 `RAG_CHUNK_OVERLAP_RATIO`로 오버랩 비율을 제어하고, 미설정 또는 잘못된 값일 때는 안전한 기본값(0.1)을 사용한다.
- `build_jsonl_records_from_pages`와 `build_documents_from_pages`가 명시적 `chunk_overlap` 값을 받지 않은 경우 자동으로 비율 기반 오버랩을 적용한다.
- 청크 크기가 변경되더라도 비율 기반 계산으로 오버랩 길이가 자연스럽게 따라오도록 만든다.

## 3. 구현 메모
- `backend/notions/ragTransform.py`
  - `_load_chunk_overlap_ratio()`로 환경 변수를 파싱하고 음수 입력을 방지한다.
  - `_calculate_chunk_overlap()`에서 비율 기반 길이를 계산하며, 전체 청크를 덮어쓰지 않도록 `chunk_size - 1`로 상한을 둔다.
  - 기존 함수 시그니처는 유지하되, 내부적으로 오버랩 비율을 계산하도록 리팩터링했다.
- README에 `RAG_CHUNK_OVERLAP_RATIO` 사용법을 문서화하여 배포시 참고할 수 있게 했다.

## 4. 테스트 노트
- 단위 테스트는 제공되지 않아 수동 확인으로 대체했다.
- 환경 변수를 미설정/유효값/잘못된 값으로 각각 실행하여 오버랩 길이가 기대대로 계산되는지 확인했다.
