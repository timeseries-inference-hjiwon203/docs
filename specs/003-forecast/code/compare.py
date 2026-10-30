"""여러 실험의 60분 오차를 한 표로. 기본은 검증(9월)만 본다.

    python compare.py E1 E1a E1b E1c
    python compare.py --test E1c E2 E4_tcn_2h   # 시험(10월) 참고표. runs/selected.json이 있어야 하고,
                                                # 각 실험을 evaluate.py --final로 먼저 채점해 test_mae.csv가 있어야 한다
"""

# 수정 기록
# - 2026-10-25 처음 작성
# - 2026-10-25 학습 공간·공간 입력 칸 추가 (E6)
# - 2026-10-25 --test 추가 (최종 모델 고정 뒤 다른 실험의 시험 결과를 참고로 보기. 고르기에는 쓰지 않는다)

import json
import os
import sys

import pandas as pd

args = sys.argv[1:]
split = "test" if "--test" in args else "val"
names = [a for a in args if a != "--test"]
if split == "test" and not os.path.exists("runs/selected.json"):
    raise SystemExit("시험 기간은 runs/selected.json이 있어야 본다 (plan.md '평가')")

base = pd.read_csv("data/baseline_mae.csv")
pers = base[(base["split"] == split) & (base["baseline"] == "persistence") & (base["horizon_min"] == 60)]
pers = pers.set_index(["location", "measurement"])["MAE"]

rows = []
for name in names:
    with open(f"runs/{name}/config.json") as f:
        cfg = json.load(f)
    hist = pd.read_csv(f"runs/{name}/history.csv")
    mae = pd.read_csv(f"runs/{name}/{split}_mae.csv")
    m60 = mae[mae["horizon_min"] == 60].set_index(["location", "measurement"])["MAE"]
    row = {"실험": name, "모델": cfg["model"], "과거(시간)": cfg["history_bins"] // 12,
           "일정": "O" if cfg["use_schedule"] else "X", "lr": cfg["lr"], "dropout": cfg.get("dropout", 0),
           "wd": cfg.get("weight_decay", 0), "계절": "O" if cfg.get("season") else "X",
           "학습 공간": "+".join(cfg.get("train_locations", ["실습실", "회의실"])),
           "공간 입력": "O" if cfg.get("location_input", True) else "X",
           "최고 에폭": int(hist.loc[hist["val_score"].idxmin(), "epoch"]) if "val_score" in hist else None}
    for (loc, m), v in m60.items():
        row[f"{loc} {'CO₂' if m == 'co2' else '온도'}"] = f"{v:.3g} ({100 * (1 - v / pers[(loc, m)]):+.0f}%)"
    row["점수"] = round(float((m60 / pers.reindex(m60.index)).mean()), 3)
    rows.append(row)

pd.set_option("display.width", 250)
label = "시험(10월) 참고표 — 최종 모델은 selected.json 그대로" if split == "test" else "검증(9월)"
print(f"{label} 60분 뒤 MAE (현재값 유지보다 작아진 %). 점수 = 현재값 유지 대비 비율 평균, 작을수록 좋음")
print(pd.DataFrame(rows).to_string(index=False))
