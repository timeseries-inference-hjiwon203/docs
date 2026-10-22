# 과제 2 분석 코드 안내

<!-- 수정 기록
- 2026-10-22 patterns.py와 결과 파일 추가
-->

Mac의 `~/Downloads/project/timeseries-inference/002-baseline/`에 두고, 가상환경(`source ~/venvs/timeseries/bin/activate`)을 켠 뒤 실행한다.

## 흐름

```
aip-1 InfluxDB ──(scan_all.py)──▶ data/raw/*.csv.gz   원본 그대로, 달별 저장
                                       │
                                  clean.py 규칙          버릴 값 거르기
                                       │
                               (resample.py)──▶ data/grid_5min.csv.gz   5분 칸 표
                                       │
                                 (split.py)──▶ data/norm_stats.json     기간 나누기, 정규화 값
                                       │
                             (baselines.py)──▶ data/baseline_mae.csv    기준선 성능표
                                               data/eval_points.csv.gz  채점 시점 목록
                              (patterns.py)──▶ data/fig_pattern_*.png   시간대별 패턴 그래프
                                               data/day_summary.csv     하루마다 반응 시간, 안 맞는 날
```

## 코드 파일

| 파일 | 역할 | DB 접속 | 다른 파일이 가져다 씀 |
|---|---|---|---|
| `load_day.py` | DB에서 정해진 기간을 읽는 함수(`load`). 단독 실행하면 하루 치 요약 | 예(토큰 필요) | scan_all |
| `scan_all.py` | 2025-08부터 한 달씩 읽어 `data/raw/`에 저장, 센서별 값 범위·재전송 수 요약 | 예(새 달만) | |
| `extremes.py` | 저장된 원본에서 CO₂ 3,000 초과 사건, 10℃ 미만인 날 찾기. `read_cache` 함수 제공 | 아니요 | clean, resample, show |
| `show.py` | 한 공간·한 항목의 원본 값을 시각 순서대로 보기 (의심 구간 확인용) | 아니요 | |
| `clean.py` | **정제 규칙** 1~5. 과제 8 서비스에서도 그대로 씀 | 아니요 | resample |
| `resample.py` | 5분 칸 만들기, 실습실 4개 센서 중앙값, 15분까지 채우기, 빈칸 길이 표 | 아니요 | |
| `split.py` | **학습·검증·시험 기간**, 학습 기간 정규화 값. 과제 3~6에서도 그대로 씀 | 아니요 | baselines |
| `baselines.py` | 기준선 3종 × 5·15·30·60분 × CO₂·온도 MAE, 채점 시점 목록 저장 | 아니요 | |
| `patterns.py` | 시간대별 평균 그래프, 실습실 수업일 CO₂ 반응 시간, 일정과 안 맞는 날 | 아니요 | |

## 결과 파일 (`data/`, Mac에만 있음, git에 올리지 않음)

| 파일 | 내용 |
|---|---|
| `raw/YYYY-MM.csv.gz` | DB 원본 한 달 치 |
| `scan_summary.csv` | 센서별 전체 기간 요약 |
| `co2_high_events.csv` | CO₂ 3,000 초과 사건 목록 |
| `clean_report.csv` | 정제 규칙별 버린 건수 |
| `grid_5min.csv.gz` | 5분 칸 표 (채운 값 + `real_*` 진짜 값 여부 + `n_*` 센서 수) |
| `norm_stats.json` | 학습 기간 평균·표준편차 |
| `baseline_mae.csv` | 기준선 성능표 |
| `eval_points.csv.gz` | 채점한 시점 목록 (과제 3·6이 같은 시점에서 채점) |
| `fig_pattern_<공간>_<항목>.png` | 시간대별 평균 그래프 (수업일 시기별 + 쉬는 날) |
| `day_summary.csv` | 실습실 하루마다 아침 기준값, 오르기 시작한 시각, 변화 폭, 일정과 안 맞음 여부 |

규칙과 그 이유는 `../notes.md` 맨 위 "확정한 규칙과 이유"에 있다.
