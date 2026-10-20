---

description: "과제 1 데이터 수집 체계 할 일 목록"
---

# Tasks: 데이터 수집 체계 (과제 1)

**Input**: [spec.md](spec.md), [plan.md](plan.md)

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 동시에 해도 되는 일
- **[Story]**: 어느 User Story에 속하는지 (US1~US4)

## Phase 1: Setup (준비)

- [x] T001 aip-1에서 `mosquitto_sub`로 `data.withio.net:1883` 접속 확인
- [ ] T002 `mosquitto_sub`로 토픽 구조와 메시지 예시를 확인해 `spec.md` FR-001에 채운다
- [ ] T003 aip-1에 InfluxDB 2.x 설치, `curl -i http://localhost:8086/ping`이 `204`인지 확인
- [ ] T004 InfluxDB에 내 계정·org·버킷·토큰을 만든다
- [ ] T005 aip-1에 Telegraf 설치
- [ ] T006 [P] 설치한 프로그램을 노션 설치 기록표에 적는다

## Phase 2: User Story 1 - 받아서 저장 (P1) 🎯 MVP

- [ ] T007 [US1] Telegraf 시험 설정(출력은 화면)으로 메시지가 원하는 모양으로 풀리는지 확인
- [ ] T008 [US1] 출력을 InfluxDB(내 버킷)로 바꾸고, client ID는 나만 쓰는 이름으로 정한다
- [ ] T009 [US1] 10분 실행 후 4공간 × 3항목 값이 쌓였는지 확인

**Checkpoint**: 데이터가 쌓인다

## Phase 3: User Story 2 - 자동 복구 (P1)

- [ ] T010 [US2] Telegraf를 서비스로 등록해 부팅 시 자동 시작되게 한다 (방법 미정)
- [ ] T011 [US2] 시험 1: 수집 중 브로커/네트워크를 끊었다 다시 연결 → 1분 안에 재개되는지 기록
- [ ] T012 [US2] 시험 2: 보드 재부팅 → 자동 재개되는지 기록

## Phase 4: User Story 3 - 수집 현황 (P2)

- [ ] T013 [US3] 공간·항목별 건수, 마지막 수신 시각, 24시간 커버율, 결측 구간을 보는 방법을 정하고 만든다
- [ ] T014 [US3] 24시간 수집 후 현황 표를 `report.md`에 붙이고, 빠진 구간의 원인을 적는다

## Phase 5: User Story 4 - 설정으로 형식 변경 대응 (P2)

- [ ] T015 [US4] 형식 변경 상황 하나를 가정한다
- [ ] T016 [US4] Telegraf 설정만 고쳐 대응하고, 무엇을 바꿨는지 `report.md`에 기록한다

## Phase 6: 마무리 · 심화(B, 선택)

- [ ] T017 `ROADMAP.md`의 과제 1 상태를 갱신한다
- [ ] T018 [P] (B) 1년 뒤 저장소 크기 추정, 다운샘플링·보관 정책 설계
- [ ] T019 [P] (B) 같은 메시지가 두 번 오는 경우 찾아내고 처리
