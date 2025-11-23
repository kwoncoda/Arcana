---
id: EPIC-001
type: prd
title: Arcana MVP — PRD
status: ready
owner: product
updated: 2025-09-26
links:
---
# Arcana MVP — PRD


## 1. 배경/문제
사내에 여러가지 협업툴을 이용해서 데이터를 저장하는데 그렇게 되면 문서를 찾는데 어려움을 겪음.
노션, 로컬에 있는 데이터 등 여러 곳에서 데이터를 가져와 맥락을 통한 검색을 하도록 함.
검색 이후 맥락을 이용한 문서 생성을 편하게 하도록 함. 
Arcana는 **검색→맥락 합성→문서 생성**을 하나의 흐름으로 제공.


## 2. 목표/KPI(핵심성과지표)
- 검색/답변 p50 ≤ 2.5s, p95 ≤ 6s
- 근거 클릭률 ≥ 25%
- 7일 내 활성 조직 비율 ≥ 60%
- 템플릿 생성 사용률 ≥ 30%


## 3. 범위(MVP)
- **Must**: Notion 연동, 조직 단일 RAG 인덱스, 검색/근거, 템플릿(회의요약/주간리포트)
- **Should**: 스코프 검색(특정 페이지/DB), 인덱싱 제외 규칙
- **Won’t**: Slack/Local, 감사로그, 다문서 동시 생성 풀스펙

## 4. 리스크/가정
- Notion API 속도/제한 → 증분/큐/백오프
- 정확성 편차 → 근거 우선/답변 길이 제한

## B. 데이터 모델(요약)
- organizations(idx, name, created)
- users(idx, email, id, username, password_hash, type, active, created, last_login)
- memberships(idx, user_idx, org_idx, role, created)
- data_sources(idx, org_idx, type='notion|local', name, status, synced, created)
- notion_credentials(idx, user_idx, data_source_idx, provider, bot_id, provider_workspace_id, workspace_name, workspace_icon, token_type, access_token_enc, refresh_token_enc, expires, created, updated, provider_payload)
- documents(idx, org_idx, data_source_idx, external_id, title, url, last_edited_time, last_synced, created)
- chunks(idx, doc_idx, ord, text, token_count, created)
- embeddings_index(idx, org_idx, chunk_idx, vector_id, created, updated)
- notion_sync_state(idx, data_source_idx, last_full_sync, since, next_cursor, rate_limited_until, created, updated)

## C. 비기능 요구(NFR)
- 성능: 검색 p50≤2.5s/p95≤6s
- 보안: JWT, org 스코프 필수, OAuth 토큰 암호화 저장
- 운영: 재인덱싱 트리거, 상태 확인 API

## E. 구현 규칙
- Java에서 boolean `is*`/timestamp `*At` 지양 → 과거형/상태형(`active`, `created`) 사용