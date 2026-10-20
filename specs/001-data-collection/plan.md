# Implementation Plan: 데이터 수집 체계 (과제 1)

**Branch**: `001-data-collection` | **Date**: 2026-10-20 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/001-data-collection/spec.md`

## Summary

파이썬 수집기 하나가 MQTT 토픽을 구독하고, 설정 파일(YAML)에 적힌 매핑대로 메시지를 풀어
InfluxDB에 쓴다. systemd 서비스로 등록해 재부팅·장애 후에도 자동으로 다시 돈다.
현황 스크립트가 InfluxDB를 조회해 커버율 표를 만든다.

## Technical Context

**Language/Version**: Python 3 (Jetson 기본 파이썬, 가상환경 사용)

**Primary Dependencies**: `paho-mqtt`(MQTT 구독), `influxdb-client`(2.x 기준, 버전 확인 후 조정), `PyYAML`(설정), `pandas`(현황 표)

**Storage**: InfluxDB `data.withio.net:8086` [NEEDS CLARIFICATION: 버전·org·bucket·접속 가능 네트워크]

**Testing**: `pytest`로 메시지 파싱·매핑 단위 테스트, 브로커 끊기/재부팅 시험은 수동 체크리스트

**Target Platform**: Jetson Orin Nano (Ubuntu/JetPack), systemd

**Project Type**: 상시 실행 서비스(daemon) + 명령줄 도구

**Performance Goals**: 4공간 × 3항목 × 1분 주기 = 분당 12건 수준. 성능 부담은 거의 없다

**Constraints**: 재접속 1분 이내, 커버율 95% 이상, 비밀값은 `.env`로만

**Scale/Scope**: 공간 4개, 센서 항목 3개(추가 가능)

## Constitution Check

| 원칙 | 이 과제에서 지키는 방법 | 통과 |
|---|---|---|
| V. 사람 손 없이 계속 돈다 | paho-mqtt 자동 재접속 + systemd `Restart=always` + 부팅 시 자동 시작 | ✅ |
| VI. 설정으로 바꾼다 | 토픽·필드 매핑을 `config/collector.yaml`로 분리 | ✅ |
| IV. 측정 조건 기록 | 수집 현황 보고에 기간·실/합성 여부 기재 | ✅ |
| 보안 | 토큰은 `.env`, `.gitignore`에 추가 | ✅ |
| VII. 단순하게 | 파일 3개(수집기, 현황, 설정)로 시작 | ✅ |

## Project Structure

### Documentation (this feature)

```text
specs/001-data-collection/
├── spec.md      # 무엇을 만드나
├── plan.md      # 이 파일
├── tasks.md     # 할 일 목록
└── report.md    # (나중에) 수집 현황 보고 · 형식 변경 대응 기록
```

### Source Code (코드 저장소 쪽, 예정)

```text
collector/
├── collector.py        # MQTT 구독 → 매핑 → InfluxDB 쓰기
├── status.py           # 공간·항목별 건수, 마지막 수신, 커버율, 결측 구간
└── mapping.py          # 설정 파일을 읽어 메시지를 측정값으로 바꾸는 부분
config/
└── collector.yaml      # 브로커·토픽·필드 매핑
deploy/
└── collector.service   # systemd 등록 파일
tests/
└── test_mapping.py
.env.example            # INFLUX_URL, INFLUX_TOKEN 등 (실제 값은 .env, git 제외)
```

**Structure Decision**: 이 `docs` 저장소에는 계획·보고만 둔다. 코드는 팀 코드 저장소에 위 구조로 만든다.

## 설계 결정 (생각해 볼 점에 대한 답)

- **시각은 무엇을 저장하나?** 센서 시각을 기본 시각(`_time`)으로 쓰고, 수신 시각은 별도 필드로 저장한다. 네트워크가 밀려 한꺼번에 와도 실제 측정 시점이 유지되고, 지연 정도도 알 수 있다.
- **수집과 학습이 같은 저장소를 동시에 쓰면?** 큰 조회가 쓰기를 느리게 할 수 있고, 학습 중 데이터가 계속 바뀐다. 학습은 기간을 고정해 CSV/Parquet로 내려받은 사본으로 한다.

## Complexity Tracking

해당 없음.
