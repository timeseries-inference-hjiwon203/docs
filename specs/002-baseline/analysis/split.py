"""학습·검증·시험 기간과 정규화 값. 과제 3~6도 이 파일을 그대로 가져다 쓴다.

기간(2026-10-22 지원 결정, 한국 시각, 시작 포함·끝 미포함):
  학습 2025-09-03 ~ 2026-08-31   (이전 기수 + 45~50명 시기)
  검증 2026-09-01 ~ 2026-09-30   (45~50명 시기 마지막 달)
  시험 2026-10-01 ~ 2026-10-21   (17명 시기. 과제 8 서비스가 실제로 만나는 조건)
시간 순서로 자른다. 섞으면 모델이 이미 본 미래로 과거를 맞히게 돼 점수가 실제보다 좋게 나온다.

정규화 값(평균·표준편차)은 학습 기간의 진짜 측정값(real_*)으로만 계산한다 (SC-001).

사용법:
    python split.py     # 기간별 칸 수를 보여 주고 data/norm_stats.json 을 저장한다
"""

# 수정 기록
# - 2026-10-22 처음 작성 (기간 경계, 학습 기간 정규화 값)

import json

import pandas as pd

TZ = "Asia/Seoul"
SPLITS = {
    "train": (pd.Timestamp("2025-09-03", tz=TZ), pd.Timestamp("2026-09-01", tz=TZ)),
    "val": (pd.Timestamp("2026-09-01", tz=TZ), pd.Timestamp("2026-10-01", tz=TZ)),
    "test": (pd.Timestamp("2026-10-01", tz=TZ), pd.Timestamp("2026-10-22", tz=TZ)),
}
MEASUREMENTS = ["co2", "temperature", "humidity"]


def read_grid(path="data/grid_5min.csv.gz"):
    g = pd.read_csv(path)
    g["bin"] = pd.to_datetime(g["bin"], utc=True, format="ISO8601").dt.tz_convert(TZ)
    return g


def which_split(times):
    """시각마다 train/val/test/"" 중 어디에 속하는지."""
    out = pd.Series("", index=times.index)
    for name, (start, stop) in SPLITS.items():
        out[(times >= start) & (times < stop)] = name
    return out


def norm_stats(grid):
    train = grid[which_split(grid["bin"]) == "train"]
    stats = {}
    for loc, g in train.groupby("location"):
        stats[loc] = {}
        for m in MEASUREMENTS:
            v = g.loc[g["real_" + m], m]
            stats[loc][m] = {"mean": round(float(v.mean()), 4), "std": round(float(v.std()), 4), "n": int(len(v))}
    return stats


if __name__ == "__main__":
    grid = read_grid()
    grid["split"] = which_split(grid["bin"])
    print("== 기간별 5분 칸 수 (real = 진짜 CO₂ 측정값이 있는 칸) ==")
    print(grid.groupby(["location", "split"]).agg(bins=("bin", "size"), real_co2=("real_co2", "sum")).to_string())

    stats = norm_stats(grid)
    with open("data/norm_stats.json", "w") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)
    print("\n== 학습 기간 정규화 값 → data/norm_stats.json ==")
    print(json.dumps(stats, ensure_ascii=False, indent=2))
