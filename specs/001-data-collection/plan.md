# Implementation Plan: 데이터 수집 체계 (과제 1)

**Branch**: `001-data-collection` | **Date**: 2026-10-21 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/001-data-collection/spec.md`

## Summary

운영진 InfluxDB(`iot-bucket`)에서 실습실·회의실의 CO₂·온도·습도 값만 골라
Jetson(aip-1)의 InfluxDB 2.x 내 버킷으로 옮긴다.
옮기기 프로그램과 InfluxDB는 서비스로 돌아서 재부팅 뒤에도 자동으로 시작된다.

## Technical Context

**원본**: 운영진 InfluxDB OSS v2.7.12, `http://10.116.64.13:8086`, 버킷 `iot-bucket`. 읽기만 함

**필터**: `location` ∈ {`실습실`, `회의실`}, `_measurement` ∈ {`co2`, `temperature`, `humidity`}, 모든 장치. 태그 `location`, `device_id`, `point` 유지

**옮기는 방법**: 미정 (InfluxDB task / Python 스크립트)

**Storage**: aip-1에 설치한 InfluxDB 2.x. 서버 1개, org 1개, 사람마다 버킷 1개(`jiwon`, `seohyun`), 자기 버킷만 읽고 쓰는 토큰 1개

**Language/Version**: 과제 2부터 Python. 과제 1 옮기기 프로그램 언어는 옮기는 방법에 따라 미정

**Testing**: 미정

**Target Platform**: Jetson Orin Nano (aip-1)

**Project Type**: 상시 실행 데이터 옮기기 서비스

**Constraints**: 커버율 95% 이상(장치별 자기 간격 기준), 비밀값은 git에 올리지 않음, 운영진 DB에는 쓰지 않음

**Scale/Scope**: 공간 2개, 장치 9개(실습실 8, 회의실 1), 항목 3개. 최근 1시간에 약 820건

## 저장 용량 (심화 B, 추정치)

- 하루 약 2만 건, 1년 약 720만 건
- 1건당 넉넉히 50바이트로 잡으면 1년 약 0.4GB/인 (실측 아님)
- aip-1 디스크 여유 88GB (2026-10-21 `df -h`, microSD)
- 보관 기간·다운샘플링 정책 → 미정

## Constitution Check

| 원칙 | 이 과제에서 지키는 방법 | 통과 |
|---|---|---|
| V. 사람 손 없이 계속 돈다 | 자동 재개 + 빠진 구간 다시 가져오기 + 서비스로 부팅 시 시작 | ✅ |
| VI. 설정으로 바꾼다 | 가져올 공간·항목 목록을 설정으로 관리 | ✅ |
| 설치 이유 기록 | InfluxDB 설치 시 이유를 노션 설치 기록표에 남김 | ✅ |

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

미정 (옮기는 방법이 정해진 뒤)

## 미정 사항

- 옮기는 방법: InfluxDB task / Python 스크립트
- 실행 주기, 처음 한 번 가져올 과거 기간
- 커버율 계산 방식 세부(장치별 기대 간격을 어떻게 정할지)
- 중복 값 처리 (심화 B)
- 사람마다 옮기기 프로그램을 따로 띄우는 방법(서비스 구성)
- 코드를 GitHub에서 Jetson으로 배포하는 방법

## Complexity Tracking

해당 없음.
