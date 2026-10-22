# Implementation Plan: 데이터 이해와 기준선 (과제 2)

<!-- 수정 기록
- 2026-10-22 미정이던 나눠 읽기·토큰·코드 위치를 정해진 대로 채움, 구조에 새 파일 반영
-->

**Branch**: `002-baseline` | **Date**: 2026-10-21 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/002-baseline/spec.md`

## Summary

aip-1 InfluxDB의 `jiwon` 버킷을 지원의 Mac에서 읽어, 정제 규칙을 정하고 데이터를 진단한 뒤
기준선 3종(현재값 유지, 최근 1시간 평균, 어제 같은 시각)의 5·15·30·60분 뒤 MAE를 잰다.
한 번 돌려 결과를 뽑는 분석이라 Jetson에서 상시로 돌리지 않는다.

## Technical Context

**데이터 원천**: aip-1 InfluxDB 2.x, org `aip-1`, 버킷 `jiwon`. Mac에서 Tailscale 주소(`100.98.23.5:8086`)로 읽기만 한다. 1년 치는 한 달씩 나눠 읽고 Mac의 `data/raw/YYYY-MM.csv.gz`에 저장해 둔다(이미 저장한 달은 다시 읽지 않음)

**분석 장소**: 지원의 Mac (Python 3.9.6, 가상환경 `~/venvs/timeseries`)

**Primary Dependencies**: pandas(표 계산), matplotlib(그래프) — Mac 가상환경에만 설치

**Language/Version**: Python 3.9.6

**토큰**: Mac에서 환경변수로만 넘긴다. 터미널을 열 때마다 `export INFLUX_TOKEN=...`으로 넣고 파일에는 저장하지 않는다

**Target Platform**: 분석은 Mac. 정제 규칙은 과제 8에서 Jetson으로 옮겨 쓴다

**Project Type**: 한 번 돌리는 분석 스크립트 + 보고서

**Scale/Scope**: 공간 2개, 항목 3개, 2025-08-08 ~ 현재 약 417만 건

**코드 위치**: Mac `~/Downloads/project/timeseries-inference/002-baseline/`(git 저장소 아님)에서 실행한다. 사본을 이 저장소 `specs/002-baseline/analysis/`에 둔다

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
├── report.md     # 데이터 진단서 + 기준선 성능표
├── notes.md      # 규칙과 이유, 작업 기록
├── troubleshooting.md
├── figures/      # 패턴 그래프
└── analysis/     # 분석 코드
```

### Source Code

`analysis/` 폴더. 파일마다 하는 일은 [analysis/README.md](analysis/README.md)

## 미정 사항

없음 (2026-10-22). 분석 간격, 센서 합치기, 분할 경계, 값 범위, 결측·재전송 처리는 notes.md "확정한 규칙과 이유"에 이유와 함께 있다.

정해진 것(2026-10-21): 분석은 Mac에서(Jetson 설치 없음), Mac이 aip-1 DB를 직접 읽음, Python 3.9.6 가상환경 + pandas·matplotlib, 회의실 예약 자료 없음, 수업 시간표 평일 09:00~18:00·점심 11:30~13:00.

## Complexity Tracking

해당 없음.
