# Implementation Plan: 데이터 이해와 기준선 (과제 2)

**Branch**: `002-baseline` | **Date**: 2026-10-21 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/002-baseline/spec.md`

## Summary

aip-1 InfluxDB의 `jiwon` 버킷을 지원의 Mac에서 읽어, 정제 규칙을 정하고 데이터를 진단한 뒤
기준선 3종(현재값 유지, 최근 1시간 평균, 어제 같은 시각)의 5·15·30·60분 뒤 MAE를 잰다.
한 번 돌려 결과를 뽑는 분석이라 Jetson에서 상시로 돌리지 않는다.

## Technical Context

**데이터 원천**: aip-1 InfluxDB 2.x, org `aip-1`, 버킷 `jiwon`. Mac에서 Tailscale 주소(`100.98.23.5:8086`)로 읽기만 한다. 1년 치는 나눠 읽는다(나누는 단위 **미정**)

**분석 장소**: 지원의 Mac (Python 3.9.6, 가상환경 `~/venvs/timeseries`)

**Primary Dependencies**: pandas(표 계산), matplotlib(그래프) — Mac 가상환경에만 설치

**Language/Version**: Python 3.9.6

**토큰**: Mac에서 환경변수로만 넘긴다. 파일에 쓰는 경우 git에 올리지 않는다(방법 **미정**)

**Target Platform**: 분석은 Mac. 정제 규칙은 과제 8에서 Jetson으로 옮겨 쓴다

**Project Type**: 한 번 돌리는 분석 스크립트 + 보고서

**Scale/Scope**: 공간 2개, 항목 3개, 2025-08-08 ~ 현재 약 417만 건

**코드 위치**: **미정** (Mac의 `timeseries-inference` 저장소에 둘지 등)

## Constitution Check

| 원칙 | 이 과제에서 지키는 방법 | 통과 |
|---|---|---|
| I. 기준선 먼저 | 이 과제가 기준선을 잰다 | ✅ |
| II. 공정한 평가 | 시간 순서 분할, 정규화는 학습 기간만, 평가 시점 목록 저장 | ✅ (계획) |
| III. 결과마다 해석 | 진단서에 "왜, 그래서 무엇을" 적기 | ✅ (계획) |
| IV. 측정 조건 기록 | 모든 표에 데이터 기간·실데이터·시험 기간 | ✅ (계획) |
| VI. 학습과 서비스는 같은 전처리 | 정제 규칙을 따로 떼어 과제 8에서 재사용 | ✅ (계획) |
| 설치 이유 기록 | 아래 "설치하는 것" 표 | ✅ |

## 설치하는 것

| 무엇 | 어디에 | 왜 지금 필요한가 | 안 깔아도 되는 경우 |
|---|---|---|---|
| pandas (표 계산 도구) | Mac 가상환경 `~/venvs/timeseries`에만 | 5분 칸 평균, 빈칸 세기·채우기, 기준선 오차(MAE) 계산을 표 단위로 한다. 과제 3~6 분석에도 계속 쓴다 | 파이썬 표준 라이브러리만으로도 계산은 되지만 코드가 훨씬 길어진다 |
| matplotlib (그래프 도구) | Mac 가상환경에만 | 진단서의 평일 시간대별 패턴 그래프, 일정–CO₂ 반응 그래프를 그린다 | 그래프 없이 표만 낼 때 |

- Jetson에는 설치하지 않는다. 과제 2는 한 번 돌려 결과를 뽑는 분석이라 상시로 돌 필요가 없고, 8GB 메모리를 여러 사람이 나눠 쓰기 때문이다.
- 가상환경에만 설치해서 Mac 전체에는 영향이 없다. 필요 없어지면 `~/venvs/timeseries` 폴더를 지우면 사라진다.

## Project Structure

### Documentation (this feature)

```text
specs/002-baseline/
├── spec.md       # 무엇을 하나
├── plan.md       # 이 파일
├── tasks.md      # 할 일 목록
└── report.md     # (나중에) 데이터 진단서 + 기준선 성능표
```

### Source Code

**미정**

## 미정 사항

- 분석 간격, 실습실 센서 합치는 방법, 분할 경계, 불가능한 값 범위, 결측 처리, 재전송 처리 (spec "정할 것")
- 나눠 읽는 단위, 읽은 데이터를 Mac에 저장해 둘지
- 코드 위치, 토큰을 Mac에 두는 방법

정해진 것(2026-10-21): 분석은 Mac에서(Jetson 설치 없음), Mac이 aip-1 DB를 직접 읽음, Python 3.9.6 가상환경 + pandas·matplotlib, 회의실 예약 자료 없음, 수업 시간표 평일 09:00~18:00·점심 11:30~13:00.

## Complexity Tracking

해당 없음.
