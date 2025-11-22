---
id: TASK-0028.1
type: task
title: 문서 생성 길이 제한 예외 처리
status: done
owner: backend
updated: 2025-10-18
---

## 1. 요청 사항
- DocumentGenerationAgent에서 max_tokens 한도(1600)로 인해 LengthFinishReasonError가 발생하여 JSON 파싱 실패로 502 오류가 전파됨.
- 기본 생성 토큰 한도를 환경변수로 키우고, 길이 초과 시 재시도 및 요약본 제공 폴백을 추가해야 함.
- system 프롬프트에 content 길이 가이드(1,500~2,000자) 추가 필요.
- 오케스트레이터가 길이/파싱 오류를 사용자 안내 메시지로 반환하도록 수정 필요.

## 2. 진행 계획
- document_generation.py에서 LLM 설정을 환경변수 기반으로 조정하고, LengthFinishReasonError 발생 시 토큰 상향→요약본 재시도 로직 추가.
- 프롬프트에 content 길이 제한 가이드라인을 반영.
- orchestrator에서 생성 실패 시 502 대신 요약 안내 메시지를 반환하도록 분기 처리.

## 3. 진행 상황
- [x] LLM 토큰 설정 및 재시도 로직 적용
- [x] 프롬프트 길이 가이드 추가
- [x] 오케스트레이터 예외 처리 개선
- [x] 테스트 및 결과 기록

## 4. 결과 요약
- 문서 생성 max_tokens를 환경변수로 제어하고 LengthFinishReasonError 시 토큰 상향→요약 재시도 폴백을 추가했습니다.
- content 길이 가이드를 프롬프트에 반영했습니다.
- 생성 실패 시 오케스트레이터가 502 대신 요약 안내 메시지를 반환하도록 분기했습니다.
