# Implementation Plan: 데이터 수집 체계 (과제 1)

**Branch**: `001-data-collection` | **Date**: 2026-10-20 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/001-data-collection/spec.md`

## Summary

Telegraf가 MQTT 브로커를 구독하고, 설정 파일에 적힌 대로 메시지를 풀어 Jetson(aip-1)의 InfluxDB 2.x에 쓴다.
Telegraf와 InfluxDB는 시스템 서비스로 돌아서 재부팅 뒤에도 자동으로 시작된다.

## Technical Context

**Language/Version**: 수집은 Telegraf 설정 파일(코드 없음). 과제 2부터는 Python

**Primary Dependencies**: Telegraf (`inputs.mqtt_consumer`, 파서, `outputs.influxdb_v2`)

**Storage**: Jetson aip-1에 설치한 InfluxDB 2.x. 서버 1개, 사람마다 계정·org·버킷

**MQTT**: `data.withio.net:1883`, 아이디·비밀번호 인증 [NEEDS CLARIFICATION: 토픽 구조, 메시지 형식]

**Testing**: 미정

**Target Platform**: Jetson Orin Nano (aip-1)

**Project Type**: 상시 실행 수집 서비스

**Constraints**: 재접속 1분 이내, 커버율 95% 이상, 비밀값은 git에 올리지 않음

**Scale/Scope**: 공간 4개, 센서 항목 3개(추가 가능)

## Constitution Check

| 원칙 | 이 과제에서 지키는 방법 | 통과 |
|---|---|---|
| V. 사람 손 없이 계속 돈다 | Telegraf 자동 재접속 + 서비스로 부팅 시 시작 | ✅ |
| VI. 설정으로 바꾼다 | 매핑을 Telegraf 설정 파일로 관리 | ✅ |
| 설치 이유 기록 | InfluxDB, Telegraf 설치 시 이유를 노션 설치 기록표에 남김 | ✅ |

## Project Structure

### Documentation (this feature)

```text
specs/001-data-collection/
├── spec.md      # 무엇을 만드나
├── plan.md      # 이 파일
├── tasks.md     # 할 일 목록
└── report.md    # (나중에) 수집 현황 보고 · 형식 변경 대응 기록
```

### Source Code

미정 (Telegraf 설정 파일을 어디에 두고 관리할지, 코드 저장소 구조)

## 미정 사항

- 저장할 시각: 센서 시각 / 수신 시각
- 깨진 메시지·저장 실패 처리 방법
- 수집 현황(커버율 표)을 만드는 방법: InfluxDB 쿼리 / Python 스크립트
- 사람마다 Telegraf를 따로 띄우는 방법(서비스 구성)
- 코드를 GitHub에서 Jetson으로 배포하는 방법

## Complexity Tracking

해당 없음.
