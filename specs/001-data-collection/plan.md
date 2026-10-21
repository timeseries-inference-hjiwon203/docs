# Implementation Plan: 데이터 수집 체계 (과제 1)

**Branch**: `001-data-collection` | **Date**: 2026-10-21 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/001-data-collection/spec.md`

## Summary

운영진 InfluxDB(`iot-bucket`)에서 실습실·회의실의 CO₂·온도·습도 값만 골라
Jetson(aip-1)의 InfluxDB 2.x 내 버킷으로 옮긴다.
옮기기 프로그램과 InfluxDB는 서비스로 돌아서 재부팅 뒤에도 자동으로 시작된다.

## Technical Context

**원본**: 운영진 InfluxDB OSS v2.7.12, 버킷 `iot-bucket`. 읽기만 함. 주소는 `https://influx.java21.net`(와이파이), 내부망 `http://10.116.64.13:8086`. 주소는 `config.json` 설정값

**필터**: `location` ∈ {`실습실`, `회의실`}, `_measurement` ∈ {`co2`, `temperature`, `humidity`}, 모든 장치. 태그 `location`, `device_id`, `point` 유지

**옮기는 방법**: Python 스크립트 `sync.py`(표준 라이브러리만 사용) + systemd timer로 1분마다 실행. 마지막으로 옮긴 시각을 `state.json`에 두고 매번 30분 겹쳐 다시 읽는다. 처음 실행 때 2025-08-08부터 하루씩 과거 데이터를 채운다

**Storage**: aip-1에 설치한 InfluxDB 2.x. 서버 1개, org 1개, 사람마다 버킷 1개(`jiwon`, `seohyun`), 자기 버킷만 읽고 쓰는 토큰 1개

**Language/Version**: Python 3 (aip-1 기본 파이썬, 추가 설치 없음)

**Testing**: 수동 시험 3가지(원본 연결 끊김, 재부팅, 설정만으로 형식 변경)와 건수 비교(`verify.py`). 결과는 `report.md`

**Target Platform**: Jetson Orin Nano (aip-1)

**Project Type**: 상시 실행 데이터 옮기기 서비스

**Constraints**: 커버율 95% 이상(장치별 자기 간격 기준), 비밀값은 git에 올리지 않음, 운영진 DB에는 쓰지 않음

**Scale/Scope**: 공간 2개, 장치 9개(실습실 8, 회의실 1), 항목 3개. 최근 1시간에 약 820건

## 저장 용량 (심화 B, 추정치)

- 하루 약 2만 건, 1년 약 720만 건
- 1건당 넉넉히 50바이트로 잡으면 1년 약 0.4GB/인 (실측 아님)
- aip-1 디스크 여유 88GB (2026-10-21 `df -h`, microSD)
- 실측(2026-10-21): 417만 건에 27MB, 1건당 약 6.8바이트 → 1년 약 48MB. 보관 정책 설계는 `report.md` 7절(삭제 설정은 적용하지 않음)

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

aip-1 `~jiwon/collector/` (코드 저장소 반영 방법은 미정)

```text
collector/
├── sync.py                  # 운영진 DB → 내 버킷 옮기기
├── status.py                # 장치별 건수·마지막 시각·커버율·빈 구간
├── verify.py                # 운영진 DB와 내 버킷 건수 비교, 전체 건수
├── config.json              # 주소, 공간·항목 매핑, 태그, 과거 시작일
├── jiwon-collector.service  # systemd: sync.py 한 번 실행 (User=jiwon)
├── jiwon-collector.timer    # systemd: 부팅 1분 뒤부터 1분마다
└── .env                     # 토큰 (권한 600, git에 올리지 않음)
```

## 미정 사항

- 원본의 ms 차이 재전송 값 처리 (심화 B)
- 코드를 GitHub에서 Jetson으로 배포하는 방법 (지금은 맥에서 scp로 복사)

정해진 것(2026-10-21): 옮기는 방법은 Python 스크립트 + systemd timer, 1분 주기, 과거는 2025-08-08부터, 커버율 칸은 장치별 보고 간격(중앙값) × 2, 사람마다 서비스 이름을 따로(`jiwon-collector`).

## Complexity Tracking

해당 없음.
