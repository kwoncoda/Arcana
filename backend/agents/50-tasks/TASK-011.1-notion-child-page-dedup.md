---
id: TASK-011.1
type: task
title: Notion child page 중첩 텍스트 제거
status: done
owner: backend
updated: 2025-10-07
---

## 요청 사항
- 부모 노션 페이지에서 child_page 블록을 순회할 때, 하위 페이지의 전체 텍스트가 중복으로 포함되지 않도록 한다.

## 진행 기록
- 2025-10-07: child_page 블록 재귀 호출을 차단하여 하위 페이지 텍스트 중복 수집 문제 해결.

## 결과
- 부모 페이지에서는 child_page의 제목만 유지하고 하위 페이지 본문은 별도 페이지로만 수집되어 JSONL 변환 시 중복이 제거됨.