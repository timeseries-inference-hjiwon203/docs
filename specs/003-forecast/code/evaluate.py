"""과제 2와 같은 채점 시점(eval_points.csv.gz)에서 모델을 채점한다.

    python evaluate.py --name E1            # 검증 기간(9월)만
    python evaluate.py --name E1 --final    # 시험 기간(10월)도. runs/selected.json이 있어야 한다

결과: runs/<이름>/val_mae.csv (--final이면 test_mae.csv), 기준선과 나란히 놓은 표를 화면에 보여 준다.
시험 기간은 고른 설정을 runs/selected.json에 적은 뒤에만 채점한다 (SC-003, plan.md '평가').
"""

# 수정 기록
# - 2026-10-25 처음 작성 (채점 시점 그대로 예측, 기준선 표와 나란히, 시험 기간 잠금)
# - 2026-10-25 season·dropout 설정을 읽도록 (없으면 꺼짐)
# - 2026-10-25 location_input 설정을 읽도록 (없으면 켜짐, E6)

import argparse
import json
import os

import numpy as np
import pandas as pd
import torch

from features import TARGETS, Data
from split import TZ

POINTS_PATH = "data/eval_points.csv.gz"
BASELINE_PATH = "data/baseline_mae.csv"


def read_points(path=POINTS_PATH):
    p = pd.read_csv(path)
    for c in ["origin", "target_time"]:
        p[c] = pd.to_datetime(p[c], utc=True, format="ISO8601").dt.tz_convert(TZ)
    return p


@torch.no_grad()
def predict_points(data, points, model=None, device="cpu", batch=2048):
    """채점 시점마다 예측값(pred)과 실제 값(actual)을 붙여 돌려준다. model=None이면 출력 0(= 변화량 방식에서 현재값 유지)."""
    points = points.copy()
    keys = points[["location", "origin"]].drop_duplicates().reset_index(drop=True)
    rows = np.concatenate([data.rows(loc, g["origin"]) for loc, g in keys.groupby("location", sort=False)])
    keys = pd.concat([g for _, g in keys.groupby("location", sort=False)], ignore_index=True)
    keys["row"] = rows

    preds = []
    if model is not None:
        model.eval()
    for i in range(0, len(keys), batch):
        past, fut, _, _, base = data.batch(keys["row"].to_numpy()[i:i + batch])
        if model is None:
            out = np.zeros((len(base), fut.shape[1], len(TARGETS)))
        else:
            out = model(torch.from_numpy(past).to(device), torch.from_numpy(fut).to(device)).cpu().numpy()
        preds.append(data.to_original(out, base))
    pred = np.concatenate(preds)                           # [기준 시각, 12, 2]

    points = points.merge(keys, on=["location", "origin"], how="left")
    key_pos = pd.Series(np.arange(len(keys)), index=pd.MultiIndex.from_frame(keys[["location", "origin"]]))
    pos = key_pos.loc[pd.MultiIndex.from_frame(points[["location", "origin"]])].to_numpy()
    step = points["horizon_min"].to_numpy() // 5 - 1
    m = points["measurement"].map({t: i for i, t in enumerate(TARGETS)}).to_numpy()
    points["pred"] = pred[pos, step, m]
    tgt = [data.target_idx[i] for i in m]
    points["actual"] = data.raw[points["row"].to_numpy() + step + 1, tgt]
    return points


def mae_table(points):
    err = (points["pred"] - points["actual"]).abs()
    return (points.assign(err=err)
            .groupby(["location", "measurement", "split", "horizon_min"])
            .agg(MAE=("err", "mean"), n=("err", "size")).reset_index())


def side_by_side(mae, split, label):
    """모델 MAE를 기준선 3종과 한 표로. 현재값 유지보다 몇 % 작은지도."""
    base = pd.read_csv(BASELINE_PATH)
    base = base[base["split"] == split].rename(columns={"baseline": "method"})
    m = mae[mae["split"] == split].assign(method=label)
    both = pd.concat([base[["location", "measurement", "method", "horizon_min", "MAE"]],
                      m[["location", "measurement", "method", "horizon_min", "MAE"]]])
    table = both.pivot_table(index=["measurement", "location", "method"], columns="horizon_min", values="MAE")
    table.columns = [f"{c}분" for c in table.columns]
    pers = base[base["method"] == "persistence"].set_index(["location", "measurement", "horizon_min"])["MAE"]
    gain = m.set_index(["location", "measurement", "horizon_min"])["MAE"]
    improve = (100 * (1 - gain / pers)).round(1).rename("현재값 유지보다 작아진 %").reset_index()
    return table.round(3), improve[improve["horizon_min"] == 60]


def load_run(name, device):
    from models import Forecaster
    with open(f"runs/{name}/config.json") as f:
        cfg = json.load(f)
    data = Data(cfg["history_bins"], cfg["use_schedule"], cfg["target"], norm_locations=cfg["norm_locations"],
                season=cfg.get("season", False), location_input=cfg.get("location_input", True))
    model = Forecaster(cfg["model"], data.n_past, data.n_future, cfg["history_bins"], dropout=cfg.get("dropout", 0.0)).to(device)
    model.load_state_dict(torch.load(f"runs/{name}/model.pt", map_location=device))
    return cfg, data, model


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True, help="runs/ 아래 실험 이름 (예: E1)")
    ap.add_argument("--final", action="store_true", help="시험 기간도 채점 (runs/selected.json 필요)")
    args = ap.parse_args()

    if args.final and not os.path.exists("runs/selected.json"):
        raise SystemExit("시험 기간은 고른 설정을 runs/selected.json에 적은 뒤에만 채점한다 (plan.md '평가')")

    device = "cuda" if torch.cuda.is_available() else "cpu"
    cfg, data, model = load_run(args.name, device)
    points = read_points()
    splits = ["val", "test"] if args.final else ["val"]
    points = points[points["split"].isin(splits)]
    mae = mae_table(predict_points(data, points, model, device))

    pd.set_option("display.width", 200)
    for split in splits:
        mae[mae["split"] == split].to_csv(f"runs/{args.name}/{split}_mae.csv", index=False)
        table, improve = side_by_side(mae, split, args.name)
        print(f"\n== {split} MAE (CO₂ ppm, 온도 ℃) — {args.name}: {cfg['model']}, 과거 {cfg['history_bins'] * 5 // 60}시간,"
              f" 일정 {'포함' if cfg['use_schedule'] else '제외'}, {cfg['target']} ==")
        print(table.to_string())
        print("\n60분 뒤, 현재값 유지보다 작아진 % (확인 기준: CO₂ 30% 이상, 온도 0% 초과)")
        print(improve.to_string(index=False))
