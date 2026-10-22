"""기준선 3종의 5·15·30·60분 뒤 CO₂·온도 오차(MAE)를 검증·시험 기간에서 잰다.

기준선 (예측 시점 t, h분 뒤 값을 맞힌다):
  persistence  현재값 유지       ŷ(t+h) = x(t)
  mean_1h      최근 1시간 평균   ŷ(t+h) = t-55분 ~ t 칸 12개의 평균
  yesterday    어제 같은 시각    ŷ(t+h) = x(t+h-24시간)

평가 시점 규칙 (모든 기준선·이후 모델이 같은 시점에서 채점받는다, SC-002):
  - 정답 칸 t+h 가 진짜 측정값(real_*)이어야 한다 (채운 값으로 채점하지 않음)
  - 세 기준선이 모두 예측값을 낼 수 있어야 한다 (x(t), 최근 1시간 중 한 칸 이상, x(t+h-24h)가 있음)
  - 평가 시점 목록은 data/eval_points.csv 로 저장해 과제 3·6에서 그대로 쓴다

사용법:
    python baselines.py
"""

# 수정 기록
# - 2026-10-22 처음 작성 (기준선 3종, 평가 시점 목록 저장)

import pandas as pd

from split import read_grid, which_split

HORIZONS = [5, 15, 30, 60]          # 분
TARGETS = ["co2", "temperature"]
STEPS_PER_DAY = 288                 # 5분 칸 하루치


def predictions(g, m, h):
    """한 공간의 칸 표 g(시간 순, 빈 칸 없이 이어진 5분 칸)에서 h분 뒤를 맞히는 세 기준선 값."""
    k = h // 5
    x = g[m]
    return pd.DataFrame({
        "origin": g["bin"],
        "target_time": g["bin"].shift(-k),
        "actual": x.shift(-k),
        "actual_real": g["real_" + m].shift(-k).eq(True),
        "persistence": x,
        "mean_1h": x.rolling(12, min_periods=1).mean(),
        "yesterday": x.shift(STEPS_PER_DAY - k),
    })


if __name__ == "__main__":
    grid = read_grid().sort_values(["location", "bin"])
    rows, points = [], []
    for loc, g in grid.groupby("location"):
        g = g.reset_index(drop=True)
        for m in TARGETS:
            for h in HORIZONS:
                p = predictions(g, m, h)
                p["split"] = which_split(p["target_time"])
                ok = (p["split"].isin(["val", "test"]) & p["actual_real"]
                      & p[["persistence", "mean_1h", "yesterday"]].notna().all(axis=1))
                p = p[ok]
                points.append(p[["origin", "target_time", "split"]].assign(location=loc, measurement=m, horizon_min=h))
                for b in ["persistence", "mean_1h", "yesterday"]:
                    for split, q in p.groupby("split"):
                        rows.append({"location": loc, "measurement": m, "split": split, "baseline": b,
                                     "horizon_min": h, "n": len(q),
                                     "MAE": round((q[b] - q["actual"]).abs().mean(), 2)})

    res = pd.DataFrame(rows)
    res.to_csv("data/baseline_mae.csv", index=False)
    pd.concat(points).to_csv("data/eval_points.csv.gz", index=False)

    pd.set_option("display.width", 200)
    table = res.pivot_table(index=["measurement", "location", "split", "baseline"],
                            columns="horizon_min", values="MAE")
    table.columns = [f"{c}분" for c in table.columns]
    print("== 기준선 MAE (CO₂ ppm, 온도 ℃). 정답이 진짜 측정값인 칸에서만 채점 ==")
    print(table.to_string())
    print("\n== 평가 시점 수 ==")
    print(res[res["baseline"] == "persistence"].pivot_table(index=["measurement", "location", "split"],
                                                             columns="horizon_min", values="n").to_string())
    print("\n저장: data/baseline_mae.csv, data/eval_points.csv.gz")
