# 과제 3 코드 안내

<!-- 수정 기록
- 2026-10-25 처음 작성
- 2026-10-25 뒤에서 돌리는 방법(nohup, python -u) 추가. -u가 없으면 로그 파일에 글이 늦게 써짐
- 2026-10-25 compare.py 추가, train.py 선택(--dropout, --weight-decay, --season) 설명
- 2026-10-30 analyze.py, compare.py --test, train.py --no-location 추가 반영. 최종 모델 실행 순서 추가
-->

Jetson aip-1 `jiwon` 계정의 `~/timeseries-inference/003-forecast/`에 두고 `~/eg2/bin/python`으로 실행한다.
`data/`에는 과제 2에서 옮긴 파일(`grid_5min.csv.gz`, `norm_stats.json`, `eval_points.csv.gz`, `baseline_mae.csv`), 같은 폴더에 `split.py`가 있어야 한다.

## 흐름

```
data/grid_5min.csv.gz ──(features.py + schedule.py)──▶ 입력 행렬 (과거 칸, 앞 60분 일정, 정답)
                                     │
                         (train.py, models.py)──▶ runs/<이름>/model.pt, config.json, history.csv, val_mae.csv
                                     │
                            (evaluate.py)──▶ 기준선과 나란히 놓은 표. --final이면 시험 기간도
```

## 파일

| 파일 | 역할 |
|---|---|
| `schedule.py` | 공휴일·휴강 목록, 기수별 인원, 칸마다 일정 숫자 4개(수업일, 수업 중, 점심, 인원) |
| `features.py` | 5분 칸 표 → 모델 입력. 정규화(학습 기간 값), 시간 sin·cos, 공간, 일정. 학습 기준 시각 고르기 |
| `models.py` | GRU·LSTM·TCN. 몸통만 다르고 출력층은 같다 |
| `train.py` | 설정 하나로 학습. 9월 점수로 멈춤 |
| `evaluate.py` | 과제 2 채점 시점에서 채점, 기준선과 비교. 시험 기간은 `runs/selected.json`이 있어야 함 |
| `check_data.py` | 학습 전 확인: 파일, 표본 하나, 출력 0 모델 = 현재값 유지 |
| `compare.py` | 여러 실험의 60분 오차를 한 표로 (`python compare.py E1 E1a E1b`). `--test`면 시험(10월) 참고표 (`selected.json` 필요, 모델 고르기에는 쓰지 않음) |
| `analyze.py` | 고정한 모델의 60분 CO₂ 오차를 시간대(수업 중·점심·수업 밖)와 시각별로 나눠 치우침을 본다 (`selected.json` 필요) |

`train.py` 선택: `--lr`(한 번에 고치는 크기), `--dropout`·`--weight-decay`(외우기 방지), `--season`(계절 입력), `--model`, `--hours`, `--no-schedule`, `--target`, `--train-locations`, `--no-location`(공간 표시 빼기, E6), `--seed`

## 실행 순서

```
~/eg2/bin/python check_data.py        # 맨 끝에 "통과"가 나와야 한다
mkdir -p runs
nohup ~/eg2/bin/python -u train.py --name E1 > runs/E1.log 2>&1 &   # 첫 모델, 뒤에서
tail -f runs/E1.log                   # 진행 보기 (Ctrl+C는 보기만 멈춤)
~/eg2/bin/python evaluate.py --name E1
```

`-u`를 빼면 파이썬이 글을 모았다가 한꺼번에 써서 로그가 한참 비어 보인다. 그때도 `runs/<이름>/history.csv`에는 에폭마다 바로 저장된다.

## 최종 모델 다시 만들기

```
~/eg2/bin/python -u train.py --name E4_tcn_2h --model tcn --hours 2 --lr 0.0003 --dropout 0.2 --weight-decay 0.0001 --season
# runs/selected.json에 E4_tcn_2h를 적은 뒤
~/eg2/bin/python evaluate.py --name E4_tcn_2h --final
~/eg2/bin/python analyze.py --name E4_tcn_2h
```

GPU 계산 순서 때문에 같은 seed로 돌려도 숫자가 아주 조금 다를 수 있다. 전체 실험 목록과 설정은 `../report.md` 3-2.
