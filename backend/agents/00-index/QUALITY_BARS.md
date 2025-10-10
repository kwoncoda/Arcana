---
id: QUALITY_BARS
type: quality
title: Quality Bars — Arcana
status: ready
updated: 2025-09-26
---
# Quality Bars — Arcana


## 성능
- **검색/답변**: p50 ≤ 2.5s, p95 ≤ 6s (Top‑k≤16, ~1e5 청크)
- **증분 동기화**: 1만 블록 기준 60분 내 완료


## 안정성/가용성
- 인덱싱 작업 재시도(최소 3회, 지수 백오프), 중단 복구 가능


## 보안/프라이버시
- 조직 경계 격리(모든 요청에 org 스코프 필수)
- Notion OAuth 토큰 **암호화 저장**(AES‑256‑GCM)


## 테스트
- 유닛: 파서/청커/임베딩/리트리버 ≥ 80% 커버리지
- 통합: Notion mock + Qdrant test container


## 접근성(웹)
- 키보드 내비게이션, 폰트 대비 WCAG AA 준수