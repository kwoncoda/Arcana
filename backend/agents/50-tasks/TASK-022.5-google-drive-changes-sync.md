---
id: TASK-0022.5
type: task
title: Google Drive Changes API 증분 동기화 구현
status: done
owner: backend
updated: 2025-10-31
---

## 요청 사항
- Google Drive Changes API를 사용해 워크스페이스 루트 폴더 이하의 파일 추가/수정/이동/삭제를 증분 동기화한다.
- 파일 콘텐츠 변경 여부를 md5Checksum(바이너리)와 version/modifiedTime(Google Docs 계열) 기준으로 판단한다.
- “오래전에 만든 문서를 오늘 업로드한 경우”도 누락되지 않도록 인덱싱한다.
- RAG 인덱스와 메타데이터를 정확히 갱신하고, 초기 상태에서는 전체 부트스트랩을 수행한다.

## 진행 기록
- 2025-10-31: Google Drive Changes API 클라이언트(`change_stream.py`)를 추가하고, 루트 트리 필터링 및 폴더 조상 탐색 로직을 구현했다.
- 2025-10-31: 증분 상태/파일 스냅샷 테이블과 SQLAlchemy 모델을 추가하여 md5Checksum·version 기반 변경 감지를 저장하도록 했다.
- 2025-10-31: `/google-drive/files/pull` 라우터를 증분 흐름으로 재구성하고, 삭제/이동 감지 시 RAG 문서를 제거하도록 확장했다.

## 결과
- Changes API 기반으로 Google Drive 워크스페이스 파일 증분 동기화가 가능하며, 신규 업로드/이동/삭제에 대응해 RAG 인덱스가 최신 상태로 유지된다.
- 파일 스냅샷 메타데이터를 활용해 불필요한 재처리를 줄이고, 제거된 문서는 벡터 스토어에서 자동 삭제된다.
