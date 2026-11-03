"""학습 전에 데이터와 입력이 제대로 만들어지는지 확인한다 (tasks T003, T006).

    python check_data.py

1. 옮긴 파일의 칸 수·채점 시점 수가 과제 2와 같은가
2. 학습 기준 시각이 공간마다 몇 개인가
3. 표본 하나(2026-10-15 13:00 실습실)를 사람이 읽을 수 있게 보여 준다
4. 출력 0 모델(= 현재값 유지)의 검증 기간 점수가 과제 2 기준선 표와 똑같은가 → 채점 코드가 맞는지 확인
"""

# 수정 기록
# - 2026-10-25 처음 작성
# - 2026-10-25 60분 변화량 표준편차(변화량 정답의 크기) 출력 추가

import pandas as pd

from evaluate import BASELINE_PATH, mae_table, predict_points, read_points
from features import LOCATIONS, Data
from split import read_grid

pd.set_option("display.width", 200)

grid = read_grid()
points = read_points()
print("== 1. 옮긴 파일 ==")
print(grid.groupby("location").agg(칸=("bin", "size"), 처음=("bin", "min"), 끝=("bin", "max")).to_string())
print(points.groupby(["split", "location", "measurement"]).size().unstack().to_string())

data = Data(history_bins=24)
print("\n== 2. 학습 기준 시각 (과거 2시간) ==")
for loc in LOCATIONS:
    print(f"  {loc}: 학습 {len(data.train_origins('train', [loc])):,}개, 검증 {len(data.train_origins('val', [loc])):,}개")
print(f"  과거 칸 숫자 {data.n_past}개: {data.past_columns}")
print(f"  미래 칸 숫자 {data.n_future}개: {data.future_columns}")
print(f"  정규화(두 공간 합침): " + ", ".join(f"{m} 평균 {mu:.2f} 표준편차 {sd:.2f}" for m, (mu, sd) in data.norm.items()))
print(f"  60분 변화량 표준편차(변화량 정답을 나누는 값): CO₂ {data.delta_std[0]:.1f} ppm, 온도 {data.delta_std[1]:.3f} ℃")

print("\n== 3. 표본 하나: 실습실 2026-10-15(목) 13:00 기준 ==")
row = data.rows("실습실", [pd.Timestamp("2026-10-15 13:00", tz="Asia/Seoul")])
past, fut, y, mask, base = data.batch(row)
p = pd.DataFrame(past[0], columns=data.past_columns)
p.insert(0, "시각", data.times[row[0] - 23: row[0] + 1].dt.strftime("%H:%M").to_numpy())
print("과거 칸 (처음 2칸과 마지막 3칸, 센서는 정규화 값):")
print(pd.concat([p.head(2), p.tail(3)]).round(2).to_string(index=False))
f = pd.DataFrame(fut[0], columns=data.future_columns)
f.insert(0, "시각", data.times[row[0] + 1: row[0] + 13].dt.strftime("%H:%M").to_numpy())
print("미래 칸 (일정만):")
print(f[["시각"] + [c for c in data.future_columns if not c.startswith(("tod", "dow"))]].round(2).to_string(index=False))
print(f"지금 값: CO₂ {base[0][0]:.1f} ppm, 온도 {base[0][1]:.2f} ℃")
actual = data.to_original(y, base)[0]
print("정답 (원래 단위): CO₂ " + " ".join(f"{v:.0f}" for v in actual[:, 0]))

print("\n== 4. 출력 0 모델 = 현재값 유지? (검증 기간) ==")
mae = mae_table(predict_points(data, points[points["split"] == "val"], model=None))
base_mae = pd.read_csv(BASELINE_PATH)
base_mae = base_mae[(base_mae["split"] == "val") & (base_mae["baseline"] == "persistence")]
cmp = mae.merge(base_mae, on=["location", "measurement", "split", "horizon_min"], suffixes=("_출력0", "_기준선"))
cmp["차이"] = (cmp["MAE_출력0"] - cmp["MAE_기준선"]).abs()
print(cmp[["location", "measurement", "horizon_min", "MAE_출력0", "MAE_기준선", "n_출력0", "n_기준선", "차이"]]
      .round(3).to_string(index=False))
print("통과" if (cmp["차이"] < 0.01).all() and (cmp["n_출력0"] == cmp["n_기준선"]).all() else "다름 — 확인 필요")
