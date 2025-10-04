---
id: TASK-TOKEN-REFRESH-API
category: backend
status: draft
title: "토큰 재발급 API 사양 정리"
updated: 2024-05-06
artifacts:
  - endpoint: POST /users/token/refresh
  - code: backend/routers/users.py
  - code: backend/schema/users.py
  - code: backend/utils/auth.py
relates_to: ["US-001.3"]
---

## 목적
- `/users/token/refresh` 엔드포인트의 계약 사항과 검증 순서를 기록한다.
- 유지보수 담당자가 토큰 회전 정책과 관련 예외 메시지를 빠르게 파악할 수 있도록 한다.

## 엔드포인트 요약
- **URL**: `POST /users/token/refresh`
- **요청 스키마**: `TokenRefreshRequest`
  - `refresh_token` (string) – 로그인 시 발급된 리프레시 토큰
- **응답 스키마**: `TokenRefreshResponse`
  - `access_token` (string)
  - `refresh_token` (string)
- **성공 상태 코드**: `200 OK`
- **실패 상태 코드**: `401 Unauthorized` (리프레시 토큰 검증 실패 시)

## 검증 절차
1. **토큰 구조 및 서명 검증** – `decode_refresh_token`이 JWT 헤더·페이로드·서명을 분리하고 HMAC-SHA256 서명을 확인한다.
2. **만료 확인** – 페이로드의 `exp` 클레임이 현재 UTC 시각 이후인지 확인한다.
3. **타입 확인** – 페이로드의 `type`이 `refresh`인지 검증한다. 잘못된 타입이면 `InvalidTokenError("리프레시 토큰이 필요합니다.")`가 발생한다.
4. **사용자 조회** – 토큰의 `sub` 값을 정수로 변환하여 `User.idx`와 매칭되는 활성 사용자만 허용한다.

## 발급 정책
- 성공 시 항상 **새로운** 액세스 토큰과 리프레시 토큰을 동시에 발급해 리프레시 토큰 회전을 강제한다.
- 사용자 계정이 비활성화된 경우(`active=False`)에는 401과 "사용자를 찾을 수 없습니다." 메시지를 반환한다.

## 예외 메시지 맵핑
| 상황 | 메시지 |
| --- | --- |
| Bearer 토큰 누락 | `Bearer 토큰이 필요합니다.` |
| 토큰 만료 | `토큰이 만료되었습니다.` |
| 토큰 타입 불일치 | `리프레시 토큰이 필요합니다.` |
| 서명 검증 실패 | `토큰 서명이 유효하지 않습니다.` |
| 사용자 미존재/비활성 | `사용자를 찾을 수 없습니다.` |

## 운영 메모
- JWT 시크릿 및 만료 시간은 환경 변수(`JWT_SECRET_KEY`, `JWT_ACCESS_TOKEN_EXPIRE_MINUTES`, `JWT_REFRESH_TOKEN_EXPIRE_DAYS`)로 관리한다.
- 예외 메시지는 FastAPI `HTTPException`의 `detail` 필드로 노출되므로, 프런트엔드는 본문을 분석해 후속 동작을 결정할 수 있다.
