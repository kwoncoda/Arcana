# 액세스 토큰 만료 대응 시나리오
**문서 버전:** 1.0  
**작성일:** 2024-05-06

---

## 1) 개요
프런트엔드 클라이언트가 보호된 API를 호출할 때 액세스 토큰 만료, 누락, 변조 상황을 어떻게 구분하고 대응하는지 정리한다.

---

## 2) 사전 조건
- 로그인 성공 시 `access_token`, `refresh_token` 한 쌍이 안전한 저장소에 보관되어 있다.
- `/users/token/refresh` 엔드포인트를 호출할 수 있다.
- 공통 API 클라이언트(axios 인터셉터 또는 fetch 래퍼)가 401 응답을 중앙에서 처리한다.

---

## 3) 기본 흐름
1. **요청 준비** – 최신 액세스 토큰을 읽어 `Authorization: Bearer <token>` 헤더로 첨부한다.
2. **응답 확인** – API 호출 후 401이 아닌 경우 그대로 반환한다. 401이면 본문을 JSON으로 파싱해 `detail` 메시지를 추출한다.
3. **상황별 분기**  
   - `detail === "Bearer 토큰이 필요합니다."` → 토큰이 누락된 상태이므로 토큰 저장소를 초기화하고 로그인 화면으로 이동한다.
   - `detail`이 `"토큰이 만료되었습니다."`, `"액세스 토큰이 필요합니다."` 등 만료/타입 관련 메시지 → 저장된 리프레시 토큰으로 `/users/token/refresh`를 호출하고 성공 시 새 토큰을 저장한 뒤 원래 요청을 한 번 재시도한다.
   - `detail`이 `"토큰 서명이 유효하지 않습니다."`, `"사용자를 찾을 수 없습니다."` 등 복구 불가 메시지 → 즉시 강제 로그아웃하고 사용자에게 재로그인을 요구한다.
4. **재시도 결과 처리** – 재시도에서도 401이면 리프레시 토큰이 더 이상 유효하지 않으므로 강제 로그아웃한다.

---

## 4) 의사 코드 예시
```ts
async function requestWithAuth(input: RequestInfo, init: RequestInit = {}) {
  const accessToken = tokenStore.getAccessToken();
  const refreshToken = tokenStore.getRefreshToken();

  const baseHeaders = new Headers(init.headers);
  if (accessToken) {
    baseHeaders.set("Authorization", `Bearer ${accessToken}`);
  }

  const firstResponse = await fetch(input, { ...init, headers: baseHeaders });
  if (firstResponse.status !== 401) {
    return firstResponse;
  }

  const { detail } = await firstResponse.clone().json().catch(() => ({ detail: null }));

  if (detail === "Bearer 토큰이 필요합니다.") {
    authStore.forceLogout();
    throw new Error("로그인이 필요합니다.");
  }

  if (detail && /토큰(이 )?만료|액세스 토큰이 필요/.test(detail)) {
    if (!refreshToken) {
      authStore.forceLogout();
      throw new Error("리프레시 토큰이 없습니다.");
    }

    const refreshResponse = await fetch("/users/token/refresh", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });

    if (!refreshResponse.ok) {
      authStore.forceLogout();
      throw new Error("토큰 재발급에 실패했습니다.");
    }

    const tokens = await refreshResponse.json();
    tokenStore.save(tokens);

    const retryHeaders = new Headers(init.headers);
    retryHeaders.set("Authorization", `Bearer ${tokens.access_token}`);

    const retryResponse = await fetch(input, { ...init, headers: retryHeaders });
    if (retryResponse.status !== 401) {
      return retryResponse;
    }
  }

  authStore.forceLogout();
  throw new Error(detail ?? "인증이 만료되었습니다.");
}
```

---

## 5) 운영 팁
- 리프레시 토큰 요청 역시 401을 반환할 수 있으므로, 실패 시 즉시 로그아웃한다.
- 로컬스토리지 등 영속 저장소를 사용할 경우 로그아웃 시 두 토큰을 모두 삭제한다.
- 여러 탭이 동시에 토큰을 재발급할 수 있으므로 브로드캐스트 채널 등을 이용해 토큰 변경 이벤트를 동기화한다.
