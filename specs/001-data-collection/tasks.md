---

description: "과제 1 데이터 수집 체계 할 일 목록"
---

# Tasks: 데이터 수집 체계 (과제 1)

**Input**: [spec.md](spec.md), [plan.md](plan.md)

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 동시에 해도 되는 일
- **[Story]**: 어느 User Story에 속하는지 (US1~US4)

## Phase 1: Setup (준비)

- [ ] T001 README / CODE_GUIDE를 읽고 MQTT 브로커 주소·포트·토픽 구조·메시지 예시를 `spec.md` FR-001에 채운다
- [ ] T002 교육장 네트워크에서 `curl -i http://data.withio.net:8086/ping`으로 InfluxDB 접속과 버전을 확인한다
- [ ] T003 InfluxDB의 org·bucket 이름을 확인해 `spec.md` FR-008에 채운다
- [ ] T004 [P] Jetson에 가상환경을 만들고 `paho-mqtt`, `influxdb-client`, `PyYAML`, `pandas`를 설치한다
- [ ] T005 [P] `.env.example`과 `.gitignore`(`.env` 제외)를 만든다

## Phase 2: Foundational (기초)

- [ ] T006 `mosquitto_sub`(또는 짧은 파이썬)로 토픽을 구독해 실제 메시지 10개를 `specs/001-data-collection/samples.txt`에 저장한다
- [ ] T007 InfluxDB에 테스트 값 1개를 쓰고 웹 UI/쿼리로 다시 읽어 본다

**Checkpoint**: 메시지를 눈으로 봤고, 저장소에 쓰고 읽을 수 있다

## Phase 3: User Story 1 - 받아서 저장 (P1) 🎯 MVP

- [ ] T008 [US1] `config/collector.yaml`에 브로커·토픽→공간·필드→항목 매핑을 적는다
- [ ] T009 [US1] `collector/mapping.py`: 메시지 1개를 (공간, 항목, 값, 센서 시각, 수신 시각)으로 바꾼다
- [ ] T010 [P] [US1] `tests/test_mapping.py`: `samples.txt`의 메시지로 매핑이 맞는지 테스트한다
- [ ] T011 [US1] `collector/collector.py`: 구독 → 매핑 → InfluxDB 쓰기. 형식이 틀린 메시지는 로그만 남기고 건너뛴다
- [ ] T012 [US1] 10분 실행 후 4공간 × 3항목 값이 쌓였는지 확인한다

**Checkpoint**: 손으로 실행하면 데이터가 쌓인다

## Phase 4: User Story 2 - 자동 복구 (P1)

- [ ] T013 [US2] 브로커 끊김 시 자동 재접속(`reconnect_delay_set`)과 InfluxDB 쓰기 실패 시 재시도를 넣는다
- [ ] T014 [US2] `deploy/collector.service`를 만들어 systemd에 등록한다(`Restart=always`, 부팅 시 시작)
- [ ] T015 [US2] 시험 1: 수집 중 네트워크/브로커를 끊었다 다시 연결 → 1분 안에 재개되는지 기록
- [ ] T016 [US2] 시험 2: 보드 재부팅 → 자동 재개되는지 기록

**Checkpoint**: 손대지 않아도 계속 돈다

## Phase 5: User Story 3 - 수집 현황 (P2)

- [ ] T017 [US3] `collector/status.py`: 공간·항목별 건수, 마지막 수신 시각, 24시간 커버율, 결측 구간 표를 출력한다
- [ ] T018 [US3] 24시간 수집 후 현황 표를 `specs/001-data-collection/report.md`에 붙이고, 빠진 구간의 원인을 적는다

## Phase 6: User Story 4 - 설정으로 형식 변경 대응 (P2)

- [ ] T019 [US4] 형식 변경 상황 하나를 가정한다(예: `co2` → `CO2_ppm`, 또는 새 센서 추가)
- [ ] T020 [US4] 설정 파일만 고쳐 대응하고, 무엇을 바꿨는지 `report.md`에 기록한다

## Phase 7: 마무리 · 심화(B, 선택)

- [ ] T021 `ROADMAP.md`의 과제 1 상태를 "완료"로 바꾼다
- [ ] T022 [P] (B) 1년 뒤 저장소 크기를 추정하고 다운샘플링·보관 정책을 설계한다
- [ ] T023 [P] (B) 같은 메시지가 두 번 오는 경우를 찾아내고 중복 없이 저장되게 한다

## 순서 요약

Setup(T001~T005) → 기초(T006~T007) → US1 → US2 → US3·US4(병행 가능) → 마무리
