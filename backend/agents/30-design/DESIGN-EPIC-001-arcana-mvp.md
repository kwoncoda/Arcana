---
id: EPIC-001
type: design
title: Arcana MVP — Design
status: in-progress
owner: backend
updated: 2025-09-26
links:
  stories: [US-001.1, US-001.2, US-001.3, US-001.4]
---
# Design — Arcana MVP

## 1) 대안 비교(임베딩/벡터DB)
| 항목 | 대안 | 장점 | 단점 | 선택 |
|---|---|---|---|---|
| VectorDB | Qdrant | 쉬운 Docker, 성능/필드필터 | 운영 학습곡선 | ✅ |
| Embedding | text-embedding-3-large | 품질 | 비용 | ✅(MVP) |

## 2) 인덱싱 시퀀스(초기/증분)
```mermaid
