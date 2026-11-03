"""설정 하나로 모델을 학습한다. 9월(검증) 점수가 10에폭 연속 안 좋아지면 멈추고 가장 좋던 때를 저장한다.

    python train.py --name E1                         # GRU, 과거 2시간, 변화량, 일정 포함 (기본값)
    python train.py --name E2 --no-schedule           # 일정·인원 빼기
    python train.py --name E3 --target absolute       # 미래 값 그대로 맞히기
    python train.py --name E4_tcn_4h --model tcn --hours 4
    python train.py --name E6_lab_only --train-locations 실습실
    python train.py --name E1b --lr 0.0003 --dropout 0.2 --weight-decay 0.0001   # 외우기 줄이기

결과: runs/<이름>/model.pt(빈칸 값), config.json(설정), history.csv(에폭마다 점수), val_mae.csv(검증 기간 채점)

검증 점수 = 9월 채점 시점(eval_points의 val)에서 60분 뒤 MAE ÷ 현재값 유지 MAE를
           학습한 공간 × (CO₂, 온도)마다 구해 평균한 값. 1.00이면 현재값 유지와 같고, 0.70이면 30% 작다.
           CO₂만 보고 고르면 온도가 나빠져도 모른다(E1). 비율로 바꾸면 ppm과 ℃를 같은 잣대로 본다.
시험 기간(10월)은 여기서 전혀 쓰지 않는다 (SC-003).
"""

# 수정 기록
# - 2026-10-25 처음 작성 (진짜 정답 칸만 MAE, 검증 점수로 멈춤, 씨앗 고정)
# - 2026-10-25 검증 점수를 'CO₂만'에서 '공간·항목마다 현재값 유지 대비 비율의 평균'으로 바꿈 (E1에서 CO₂만 보고 고르니 온도가 나빠짐).
#              print에 flush=True (nohup으로 돌릴 때 로그가 바로 보이게)
# - 2026-10-25 --dropout, --weight-decay, --season 추가 (E1 외우기·온도 개선 시험)
# - 2026-10-25 --no-location 추가 (E6: 공간 표시 입력 빼기)

import argparse
import json
import os
import random
import time

import numpy as np
import pandas as pd
import torch

from evaluate import BASELINE_PATH, mae_table, predict_points, read_points
from features import LOCATIONS, Data
from models import Forecaster, count_params


def masked_mae(out, y, mask):
    """진짜 측정값인 정답 칸만 |예측 - 정답| 평균. CO₂와 온도는 정규화된 크기라 그대로 더한다."""
    return (torch.abs(out - y) * mask).sum() / mask.sum().clamp(min=1)


def persistence_60(locations):
    b = pd.read_csv(BASELINE_PATH)
    b = b[(b["split"] == "val") & (b["baseline"] == "persistence") & (b["horizon_min"] == 60) & b["location"].isin(locations)]
    return b.set_index(["location", "measurement"])["MAE"]


def val_score(data, val_points, model, device, locations, pers):
    """(점수, 60분 MAE 표 {(공간, 항목): MAE}, 전체 MAE 표). 점수 = 현재값 유지 대비 비율의 평균"""
    mae = mae_table(predict_points(data, val_points, model, device))
    m60 = mae[(mae["horizon_min"] == 60) & mae["location"].isin(locations)].set_index(["location", "measurement"])["MAE"]
    return float((m60 / pers).mean()), m60, mae


def describe(m60):
    return "  ".join(f"{loc} {'CO₂' if m == 'co2' else '온도'} {v:.2f}" for (loc, m), v in m60.items())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True)
    ap.add_argument("--model", default="gru", choices=["gru", "lstm", "tcn"])
    ap.add_argument("--hours", type=int, default=2, choices=[1, 2, 4], help="과거를 몇 시간 볼지")
    ap.add_argument("--target", default="delta", choices=["delta", "absolute"])
    ap.add_argument("--no-schedule", action="store_true", help="일정·인원 입력 빼기")
    ap.add_argument("--train-locations", nargs="+", default=LOCATIONS, help="학습에 쓸 공간 (E6)")
    ap.add_argument("--epochs", type=int, default=100)
    ap.add_argument("--patience", type=int, default=10)
    ap.add_argument("--batch", type=int, default=256)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--dropout", type=float, default=0.0, help="학습 때 숫자 일부를 0으로 (외우기 방지)")
    ap.add_argument("--weight-decay", type=float, default=0.0, help="빈칸 값이 너무 커지지 않게 (외우기 방지)")
    ap.add_argument("--season", action="store_true", help="과거 칸에 1년 중 며칠째(계절) 추가")
    ap.add_argument("--no-location", action="store_true", help="공간 표시(is_lab) 입력 빼기 (E6)")
    args = ap.parse_args()

    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    device = "cuda" if torch.cuda.is_available() else "cpu"

    cfg = {"model": args.model, "history_bins": args.hours * 12, "target": args.target,
           "use_schedule": not args.no_schedule, "train_locations": args.train_locations,
           "norm_locations": args.train_locations, "seed": args.seed, "batch": args.batch, "lr": args.lr,
           "dropout": args.dropout, "weight_decay": args.weight_decay, "season": args.season,
           "location_input": not args.no_location,
           "device": device, "torch": torch.__version__}
    out_dir = f"runs/{args.name}"
    os.makedirs(out_dir, exist_ok=True)

    data = Data(cfg["history_bins"], cfg["use_schedule"], cfg["target"], norm_locations=cfg["norm_locations"],
                season=cfg["season"], location_input=cfg["location_input"])
    train = data.train_origins("train", args.train_locations)
    points = read_points()
    val_points = points[points["split"] == "val"]
    model = Forecaster(args.model, data.n_past, data.n_future, cfg["history_bins"], dropout=args.dropout).to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=args.weight_decay)
    cfg.update(n_train=int(len(train)), n_params=count_params(model), target_scale=data.scale.tolist(),
               past_columns=data.past_columns, future_columns=data.future_columns)
    with open(f"{out_dir}/config.json", "w") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    print(f"[{args.name}] {args.model}, 과거 {args.hours}시간, {args.target}, 일정 {'포함' if cfg['use_schedule'] else '제외'},"
          f" 학습 공간 {args.train_locations}, 학습 표본 {len(train):,}개, 빈칸 {cfg['n_params']:,}개, 장치 {device}", flush=True)

    pers = persistence_60(args.train_locations)
    best, best_epoch, history = float("inf"), 0, []
    start_score, m60, _ = val_score(data, val_points, model, device, args.train_locations, pers)
    print(f"  학습 전 검증 점수 {start_score:.3f} (변화량 방식이면 약 1.00 = 현재값 유지. 기준선 표가 반올림돼 있어 조금 다를 수 있음)  60분 MAE: {describe(m60)}", flush=True)
    for epoch in range(1, args.epochs + 1):
        t0 = time.time()
        model.train()
        order = np.random.permutation(train)
        losses = []
        for i in range(0, len(order), args.batch):
            past, fut, y, mask, _ = data.batch(order[i:i + args.batch])
            out = model(torch.from_numpy(past).to(device), torch.from_numpy(fut).to(device))
            loss = masked_mae(out, torch.from_numpy(y).to(device), torch.from_numpy(mask).to(device).float())
            opt.zero_grad()
            loss.backward()
            opt.step()
            losses.append(loss.item())
        score, m60, _ = val_score(data, val_points, model, device, args.train_locations, pers)
        history.append({"epoch": epoch, "train_loss": np.mean(losses), "val_score": score,
                        **{f"val_{loc}_{m}_60": v for (loc, m), v in m60.items()}, "sec": time.time() - t0})
        mark = ""
        if score < best:
            best, best_epoch, mark = score, epoch, "  ← 가장 좋음, 저장"
            torch.save(model.state_dict(), f"{out_dir}/model.pt")
        print(f"  에폭 {epoch:3d}  학습 오차 {np.mean(losses):.4f}  검증 점수 {score:.3f}  ({describe(m60)})"
              f"  {time.time() - t0:.0f}초{mark}", flush=True)
        pd.DataFrame(history).to_csv(f"{out_dir}/history.csv", index=False)
        if epoch - best_epoch >= args.patience:
            print(f"  {args.patience}에폭 동안 나아지지 않아 멈춤", flush=True)
            break

    model.load_state_dict(torch.load(f"{out_dir}/model.pt", map_location=device))
    _, m60, mae = val_score(data, val_points, model, device, args.train_locations, pers)
    mae.to_csv(f"{out_dir}/val_mae.csv", index=False)
    print(f"  가장 좋던 에폭 {best_epoch}, 검증 점수 {best:.3f} ({describe(m60)}). 자세한 표: python evaluate.py --name {args.name}",
          flush=True)


if __name__ == "__main__":
    main()
