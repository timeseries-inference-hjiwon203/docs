---
description: "과제 3 60분 예측 할 일 목록"
---

<!-- 수정 기록
- 2026-10-25 처음 작성
- 2026-10-25 T003·T006 완료 (Jetson check_data.py 통과)
- 2026-10-25 T001(GPU True, pandas 2.2.3 설치), T002 완료. T004·T005·T007~T009 코드 작성(Jetson과 같은 버전으로 합성 데이터 시험), LSTM·TCN도 models.py에 함께 넣음
- 2026-10-25 T018·T019 완료 (E4_tcn_2h 고정 후 시험 1회). analyze.py 작성(T020 진행 중)
- 2026-10-25 T016 완료 (E6 3개: 실습실만, 회의실만, 둘 다 공간 표시 없이)
- 2026-10-25 T020~T022 완료 (analyze.py, 원인 해석, report.md). E7은 지원 결정으로 하지 않음
- 2026-10-27 T010~T012·T014·T015·T023 체크 (지원 리포트 확인 후 요청). T020은 그래프 대신 표로 했음을 적음
- 2026-10-25 수정 기록 주석을 머리말(---) 밖으로 옮김 (머리말 안에 있으면 YAML 오류)
-->

# Tasks: 60분 예측 (과제 3)

**Input**: [spec.md](spec.md), [plan.md](plan.md)

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 동시에 해도 되는 일
- **[Story]**: 어느 User Story에 속하는지 (US1~US5)

## Phase 1: Setup (준비)

- [x] T001 Jetson `jiwon` 계정 eg2에서 `torch.cuda.is_available()`와 pandas 확인. 없는 것이 있으면 설명 후 지원 확인
- [x] T002 Jetson에 `~/timeseries-inference/003-forecast/data/` 만들고 Mac의 과제 2 결과 파일을 `scp`로 옮김 (`grid_5min.csv.gz`, `norm_stats.json`, `eval_points.csv.gz`, `baseline_mae.csv`, `split.py`, `patterns.py`)
- [x] T003 Jetson에서 옮긴 파일을 읽어 칸 수·채점 시점 수가 과제 2와 같은지 확인

## Phase 2: User Story 1 - 입력과 출력 (P1) 🎯 MVP

- [x] T004 [US1] `features.py`(+ `schedule.py`): 정규화, 시간 sin·cos, 공간, 일정(수업일·수업 중·점심), 인원
- [x] T005 [US1] `features.py`의 `Data.batch`: 기준 시각마다 과거 칸·앞 60분 일정·정답(변화량/미래 값)·정답 진짜 여부
- [x] T006 [US1] 표본 하나를 꺼내 사람이 확인 (13:00 기준 예시: 과거 11:05~13:00, 정답 13:05~14:00)

## Phase 3: User Story 2 - 학습과 기준선 비교 (P1)

- [x] T007 [US2] `models.py`: GRU·LSTM·TCN (같은 틀)
- [x] T008 [US2] `train.py`: 학습, 검증 점수로 멈춤, `runs/E1/` 저장
- [x] T009 [US2] `evaluate.py`: eval_points 검증 기간 채점, 기준선과 같은 표
- [x] T010 [US2] E1 학습·검증 점수 확인 (현재값 유지보다 나은가) — CO₂는 나음, 온도는 나빠 정답 크기·저장 점수를 고친 뒤 재실행(점수 0.865). 이어서 E1a·E1b·E1c로 E1c(0.833)를 기준 설정으로

## Phase 4: User Story 4 - 일정 정보의 가치 (P2)

- [x] T011 [US4] E2 (일정·인원 제외) 학습, E1과 검증 점수 비교 — E1c 기준으로 비교 (0.839 vs 0.833)
- [x] T012 [US2] E3 (미래 값 방식) 학습, E1과 비교 — E1c 기준으로 비교 (0.965, 온도가 크게 나빠짐)

## Phase 5: User Story 5 - 심화 B (P3)

- [x] T013 [US5] `models.py`에 LSTM, TCN 추가 (T007과 함께)
- [x] T014 [US5] E4: 3종 × 1·2·4시간 9개 학습 (`run_all.py`), 검증 점수 표 — `run_all.py` 대신 셸 스크립트(runs/run_E2E4.sh)로 실행, `compare.py`로 표. TCN 2h 최고(0.811). seed 1·2 반복도 함께
- [x] T015 [US5] E5: 최적 조합 일정 포함/제외, 회의실 따로 — 따로 돌리지 않고 E2 표(공간별 결과)로 대신함
- [x] T016 [US5] E6: 공간 빼기 시험 2개
- [ ] T017 [P] [US5] (선택) E7 한 칸씩 반복 — 지원 결정으로 하지 않음 (2026-10-25)

## Phase 6: 최종 채점 (시험 기간 한 번)

- [x] T018 고른 설정을 `selected.json`에 적고 지원 확인
- [x] T019 `evaluate.py --final`: 시험 기간 채점 (E1~E6 전부, 기준선과 같은 표). 이후 설정 변경 없음 — 2026-10-25 최종 모델 E4_tcn_2h 채점 완료 (CO₂ 둘 다 미달, 온도 둘 다 통과)

## Phase 7: User Story 3 - 공간별 분석 (P2)

- [x] T020 [US3] `analyze.py`: 공간 × 시간대별 오차, 큰 오차 사례 그래프, 9월 vs 10월 — 그래프는 만들지 않고 시간대별 표로 대신함
- [x] T021 [US3] 원인 해석 (회의실이 어려운 이유, 못 맞히는 순간)

## Phase 8: Polish (마무리)

- [x] T022 `report.md`: 모델 비교표, 공간별 분석, 일정 정보 결론, 측정 조건, 생각해 볼 점 답
- [x] T023 troubleshooting.md에 기술적 고민 기록 (생길 때마다) — 4건 기록 (온도 무시, 로그 버퍼링, 계절 입력, 10월 실패 원인)
- [ ] T024 지원 요청 시 docs 저장소에 코드·결과 올리기, ROADMAP 과제 3 상태 갱신

## Dependencies

- Phase 1 → 2 → 3 → (4, 5) → 6 → 7 → 8
- 시험 기간(T019)은 T018 확인 전에는 절대 채점하지 않는다
