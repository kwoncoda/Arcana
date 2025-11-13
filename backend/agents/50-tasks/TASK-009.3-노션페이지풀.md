---
id: TASK-0009.3
type: task
title: Notion 페이지 콘텐츠 수집 API 구현
status: done
owner: backend
updated: 2025-10-06
---

## 요청 사항
- 사용자가 공개로 설정한 노션 페이지의 텍스트 블록 데이터를 가져오는 API를 구현한다.
- Notion Pull 유틸리티 모듈을 신설하고, 라우터는 JWT 인증을 필수로 사용한다.

## 진행 기록
- 2025-10-06: 요구사항 분석 및 관련 문서 검토 완료.
- 2025-10-06: Notion 페이지 텍스트 수집 유틸(`backend/notions/notionPull.py`) 초안과 `/notion/pages/{page_id}/blocks` API 구현.
- 2025-10-06: 공유된 모든 노션 페이지를 순회해 텍스트 블록을 모으는 유틸로 개선하고, 일괄 갱신용 `POST /notion/pages/pull` 엔드포인트로 교체.
- 2025-10-06: `uv run pytest` 통과.

## 결과
- JWT 인증 사용자의 노션 연동 정보를 확인하고, 공유된 모든 페이지의 텍스트 블록을 한 번에 수집해 반환하는 API 제공.
- Notion Pull 유틸은 이미지 및 파일 블록을 제외하고 텍스트만 재귀적으로 수집하며, OAuth 토큰을 필요 시 갱신한다.
