# Arcana DB Schema Overview

이 문서는 `init/init.sql`에 정의된 Arcana 백엔드의 현재 데이터베이스 스키마를 요약합니다. MySQL 8 / InnoDB / `utf8mb4` 설정을 기준으로 합니다.

## 1. users
- **역할**: 서비스 로그인 계정을 저장합니다.
- **핵심 컬럼**
  - `id`, `email`: 고유 제약(UNIQUE)으로 중복 가입 방지.
  - `password_hash`: 해시된 비밀번호.
  - `active`, `created`, `last_login`: 계정 상태 및 감사 용도.
- **특징**: 기본키 `idx`는 내부 식별자이며, 닉네임은 선택적으로 UNIQUE 제약이 있습니다.

## 2. organizations
- **역할**: 회사/팀 단위 조직 정보를 관리합니다.
- **핵심 컬럼**: `name`과 생성 시각 `created`.
- **특징**: 별도 상태 컬럼 없이 워크스페이스 및 멤버십과 연계됩니다.

## 3. memberships
- **역할**: 사용자와 조직 사이의 소속 관계를 정의합니다.
- **핵심 컬럼**
  - `user_idx`, `organization_idx`: 각각 `users`, `organizations`를 참조하는 FK.
  - `role`: `owner`, `admin`, `member` 중 하나.
- **제약**
  - `UNIQUE (user_idx, organization_idx)`로 동일 조직 중복 가입 방지.
  - 외래키 `fk_mem_user`, `fk_mem_org`이 참조 무결성을 보장.

## 4. workspaces
- **역할**: 개인용/조직용 워크스페이스 컨테이너.
- **핵심 컬럼**
  - `type`: `personal` 또는 `organization`.
  - `owner_user_idx`, `organization_idx`: 타입에 따라 하나만 NULL이 아님.
- **제약**
  - `CHECK` 제약(`chk_ws_shape`)으로 타입별 FK 조합을 강제.
  - `UNIQUE` 제약으로 사용자·조직당 하나의 워크스페이스만 허용.

## 5. rag_indexes
- **역할**: 워크스페이스별 RAG 인덱스 메타데이터.
- **핵심 컬럼**
  - `workspace_idx`: `workspaces` FK.
  - `index_type`, `storage_uri`, `dim`, `status`, `object_count`, `vector_count`.
- **특징**: 워크스페이스 내부에서 `name`은 고유(`UNIQUE (workspace_idx, name)`). 갱신 시각은 `updated` 트리거로 자동 업데이트.

## 6. data_sources
- **역할**: 외부 데이터 소스(현재 Notion만) 연결 정보를 기록.
- **핵심 컬럼**: `workspace_idx`, `type`, `status`, `synced`.
- **특징**: 워크스페이스에 종속되며 외래키 `fk_ds_ws`로 연결됩니다.

## 7. notion_oauth_credentials
- **역할**: Notion OAuth 인증 자격증명 저장.
- **핵심 컬럼**
  - `user_idx`: 인증을 수행한 사용자 FK.
  - `data_source_idx`: 연결된 데이터 소스 FK.
  - 토큰 및 워크스페이스 메타 정보(`access_token`, `refresh_token`, `expires`, `workspace_name` 등).
- **제약**
  - `UNIQUE (provider, bot_id)`로 동일 봇 설치 중복 방지.
  - `UNIQUE (data_source_idx, user_idx)`로 데이터 소스당 사용자 매핑을 1개로 제한.

## 8. notion_data_source_sync_state
- **역할**: Notion 동기화 커서/상태 보존.
- **핵심 컬럼**: `data_source_idx`, `last_full_sync`, `since`, `next_cursor`, `rate_limited_until`.
- **특징**: 데이터 소스와 1:1 대응(`UNIQUE data_source_idx`). 증분 동기화 시각 및 레이트 리밋 정보를 추적.

## 관계 요약
- `users` ↔ `organizations`는 `memberships`를 통해 다대다 관계.
- `workspaces`는 개인(`users`) 또는 조직(`organizations`)에 소속되며, 관련 데이터 인덱스(`rag_indexes`)와 소스(`data_sources`)의 루트 컨테이너.
- `data_sources`는 인증 정보(`notion_oauth_credentials`)와 동기화 상태(`notion_data_source_sync_state`)의 부모 역할을 수행.

## 향후 고려 사항
- 데이터 소스 유형 확장 시 `data_sources.type` ENUM 및 관련 FK/제약 추가 필요.
- 토큰 저장 시 암호화/비식별화 전략을 적용해야 하며, 현재 스키마는 평문 저장을 가정합니다.
- `memberships.role` ENUM 확장이나 감사 로그 테이블 추가를 통해 권한 관리 강화 여지가 있습니다.