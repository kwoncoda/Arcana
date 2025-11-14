---
id: TASK-0014.1
type: task
title: LangGraph 기반 검색·생성 에이전트 라우팅
status: done
owner: backend
updated: 2025-10-11
---

## 요청 사항
- `/aiagent/search` 요청을 LangGraph를 통해 검색 혹은 문서 생성 플로우로 자동 라우팅한다.
- LLM이 검색·생성 여부를 판단하며, 생성이 선택되면 RAG 컨텍스트 사용 여부도 함께 결정한다.
- 노션 페이지 생성 로직을 별도 모듈(`backend/notions/notionCreate.py`)로 분리하고, 생성 결과를 API 응답에 포함한다.

## 진행 기록
- 2025-10-11: 요구사항 분석 및 기존 RAG 검색 에이전트 구조와 노션 연동 흐름 파악.
- 2025-10-11: LangGraph 기반 오케스트레이터, 의사결정/문서생성 LLM 체인, 노션 페이지 생성 모듈 초안 구현.
- 2025-10-11: `/aiagent/search` 라우터에 오케스트레이터 적용, 스키마/로그 구조 보강, 노션 생성 예외 처리 추가.

## 결과
- LangGraph 오케스트레이터가 검색과 노션 문서 생성을 판단해 실행하며, 생성 시 새 페이지 URL과 ID를 응답에 포함한다.
- 문서 생성용 LLM 체인과 Notion 페이지 생성 모듈이 추가되어 `ai_module`과 `notions` 구성이 확장되었다.

