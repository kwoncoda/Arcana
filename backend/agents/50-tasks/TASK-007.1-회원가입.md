---
id: TASK-0007.1
type: task
title: 회원가입 API 구현 (/users/register)
status: done
owner: backend
updated: 2025-10-02
artifacts:
  - code: /backend/routers/users.py
  - code: /backend/schema/users.py
  - code: /backend/utils/auth.py
relates_to: ["US-001.1"]
---

## DoD
- 요청 검증
  - `id` 중복 시 `409 Conflict`
  - `email` 중복 시 `460`
  - `nickname` 중복 시 `461`
  - `type` 유효성 검증: `personal | organization` 외 값이면 `464`
  - `type=organization` 이고 `organization_name` 미입력 시 `462`
- DB 트랜잭션
  - 신규 `users` 레코드 생성(비밀번호는 PBKDF2 해시 저장)
  - `type=personal`:
    - `workspaces(type='personal', owner_user_idx=<user.idx>)` 1개 생성
  - `type=organization`:
    - `organizations(name=<organization_name>)`가 없으면 생성(이름 UNIQUE)
    - `memberships(user_idx, organization_idx, role='member')` 생성
    - 조직용 워크스페이스가 없으면 `workspaces(type='organization', organization_idx=<org.idx>)` 1개 생성
  - flush/commit 처리, 제약조건 위반 시 `463`으로 매핑
- API 응답
  - 성공 시 `201 Created` (본문은 비워도 됨)
  - OpenAPI 문서에 위 상태코드 매핑(`409, 460, 461, 462, 463, 464`) 명시
- 테스트
  - 성공 케이스: personal/organization 각각 1건 이상
  - 실패 케이스: id/email/nickname 중복, invalid type, 조직명 누락
  - 조직 워크스페이스가 이미 존재하는 경우 재생성 안 되는지 확인
  - 트랜잭션 롤백 동작 검증(IntegrityError 시)
