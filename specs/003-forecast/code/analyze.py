"""고정한 모델의 60분 뒤 CO₂ 오차를 쪼개 본다. 모델은 바꾸지 않고 오차만 들여다본다.

    python analyze.py --name E4_tcn_2h

보는 것 (검증 9월 / 시험 10월, 공간별)
1. 수업 시간 / 점심 / 수업 밖으로 나눠 MAE와 치우침
   - 치우침 = 예측 − 실제의 평균. +이면 실제보다 높게 예측했다는 뜻
   - 실제 변화 = 60분 동안 실제로 변한 양의 평균, 예측 변화 = 모델이 예측한 변화의 평균
2. 시험 기간 실습실, 예측 대상 시각(시)별 MAE와 치우침
3. 학습 기간에 나온 인원 값들 (10월 17명을 학습 때 본 적이 있는지)

결과: runs/<이름>/analysis_by_period.csv, analysis_by_hour.csv
시험 기간은 runs/selected.json이 있어야 본다 (evaluate.py와 같은 규칙).
"""

# 수정 기록
# - 2026-10-25 처음 작성 (10월 시험에서 실습실 CO₂ 60분이 현재값 유지보다 나빠진 이유 확인용)

import argparse
import os

import numpy as np
import pandas as pd
import torch

from evaluate import load_run, predict_points, read_points
from schedule import headcount, schedule_columns
from split import TZ


def period_of(times):
    s = schedule_columns(times.reset_index(drop=True))
    out = np.where(s["in_class"] == 1, "수업 중", np.where(s["lunch"] == 1, "점심", "수업 밖"))
    return pd.Series(out, index=times.index)


def summarize(p, keys):
    return (p.groupby(keys)
            .agg(n=("err", "size"), 모델_MAE=("abs_err", "mean"), 유지_MAE=("pers_abs_err", "mean"),
                 치우침=("err", "mean"), 실제_변화=("actual_change", "mean"), 예측_변화=("pred_change", "mean"))
            .round(2).reset_index())


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True)
    args = ap.parse_args()
    if not os.path.exists("runs/selected.json"):
        raise SystemExit("시험 기간은 runs/selected.json이 있어야 본다 (plan.md '평가')")

    device = "cuda" if torch.cuda.is_available() else "cpu"
    cfg, data, model = load_run(args.name, device)
    points = read_points()
    points = points[points["split"].isin(["val", "test"]) & (points["measurement"] == "co2")
                    & (points["horizon_min"] == 60)]

    p = predict_points(data, points, model, device)
    pers = predict_points(data, points, None, device)       # 출력 0 = 현재값 유지 (변화량 방식)
    if cfg["target"] != "delta":
        raise SystemExit("현재값 유지 비교는 변화량(delta) 방식 모델에서만 맞다")
    p["pers"] = pers["pred"].to_numpy()
    p["err"] = p["pred"] - p["actual"]
    p["abs_err"] = p["err"].abs()
    p["pers_abs_err"] = (p["pers"] - p["actual"]).abs()
    p["actual_change"] = p["actual"] - p["pers"]
    p["pred_change"] = p["pred"] - p["pers"]
    p["시간대"] = period_of(p["target_time"])
    p["시"] = p["target_time"].dt.tz_convert(TZ).dt.hour

    pd.set_option("display.width", 200)
    by_period = summarize(p, ["split", "location", "시간대"])
    print("== 60분 뒤 CO₂, 시간대별 (ppm). 치우침 +면 실제보다 높게 예측 ==")
    print(by_period.to_string(index=False))

    lab_test = p[(p["split"] == "test") & (p["location"] == "실습실")]
    by_hour = summarize(lab_test, ["시"])
    print("\n== 시험(10월) 실습실, 예측 대상 시각별 ==")
    print(by_hour.to_string(index=False))

    train_times = data.times[(data.times >= pd.Timestamp("2025-09-03", tz=TZ)) & (data.times < pd.Timestamp("2026-09-01", tz=TZ))]
    on_class = schedule_columns(train_times.reset_index(drop=True))["in_class"].to_numpy() == 1
    seen = sorted(set(headcount(train_times.reset_index(drop=True))[on_class].astype(int)))
    print(f"\n학습 기간 수업 시간에 나온 인원: {seen}명 / 시험 기간 인원: 17명")

    by_period.to_csv(f"runs/{args.name}/analysis_by_period.csv", index=False)
    by_hour.to_csv(f"runs/{args.name}/analysis_by_hour.csv", index=False)
