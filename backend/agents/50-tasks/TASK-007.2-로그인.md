---
id: TASK-0007.2
type: task
title: 로그인 API 구현 (/users/login)
status: done
owner: backend
updated: 2025-10-02
artifacts:
  - code: /backend/routers/users.py
  - code: /backend/schema/users.py
  - code: /backend/utils/auth.py
relates_to: ["US-001.2"]
---

## DoD
- 인증 로직
  - `select(User).where(User.id == payload.id)`로 사용자 조회
  - 사용자 미존재 시에도 더미 해시(`_DUMMY_HASH`)로 `verify_password` 수행 → 타이밍 균등화
  - 실패 조건(사용자 없음/비번 불일치/비활성) 모두 `401 Unauthorized` + 동일 메시지로 통일
  - 실패 시 `WWW-Authenticate: Bearer` 헤더 포함
- 상태 갱신
  - 성공 시 `users.last_login = datetime.utcnow()` 갱신 후 commit (예외 시 rollback)
- 토큰 발급
  - `create_access_token(subject=str(user.idx))`
  - `create_refresh_token(subject=str(user.idx))`
  - 성공 응답 `200 OK`에 `access_token`, `refresh_token` 반환
- 테스트
  - 성공: 올바른 자격증명 → 200, 두 토큰 존재, `last_login` 갱신
  - 실패: 사용자 없음 / 비번 불일치 / 비활성 → 모두 401, 동일 메시지, 헤더 포함
  - 예외: 커밋 실패 시 rollback 수행 확인
- 문서화
  - OpenAPI에 성공/실패(200/401) 응답 스펙 및 헤더 기술
