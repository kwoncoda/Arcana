---
id: TASK-0029.1
type: task
title: 노션 테이블 블록 변환 추가
status: done
owner: backend
updated: 2025-10-21
---

## 1. 요청 사항
- 마크다운 표를 노션에 생성할 때 일반 문단 블록으로만 변환되어 파이프(`|`)와 하이픈(`-`)이 그대로 노출됨.
- Notion API에서 표로 렌더링되도록 table/table_row 블록 생성 로직이 필요함.

## 2. 진행 계획
- 마크다운 테이블 헤더와 바디를 파싱하는 헬퍼를 추가하고, table 및 table_row 블록을 만들어 children에 포함.
- 기존 마크다운 블록 파서를 테이블 감지 시 분기하도록 개선해 표 구조를 유지.

## 3. 진행 상황
- [x] 마크다운 테이블 셀 파싱 및 블록 생성 헬퍼 추가
- [x] 블록 파서에 테이블 감지 로직 통합

## 4. 결과 요약
- `notionCreate._markdown_to_blocks`가 헤더/구분선 패턴을 감지해 Notion table + table_row 블록을 생성하도록 수정하여, 노션에서 표로 렌더링되도록 개선함.
