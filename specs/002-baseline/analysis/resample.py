"""정제한 원본을 5분 칸으로 맞추고, 빈칸이 몇 칸짜리로 얼마나 있는지 보여 준다.

만드는 방법:
  1. clean.py 규칙으로 정제한다
  2. 센서마다 5분 칸 평균을 낸다 (1분 센서가 칸 안에 기록이 많아도 한 표만 갖게)
  3. 실습실은 처음부터 있던 센서 4개(BASE_DEVICES)의 중앙값을 공간 값으로 쓴다(4번 채우기 뒤). 회의실은 센서 1개 그대로
  4. 빈칸은 센서마다 앞 값으로 최대 3칸(15분)까지 채운 뒤 중앙값을 낸다. 더 길면 비워 둔다(NaN)
     실시간 서비스도 "마지막 값을 15분까지 유지"는 똑같이 할 수 있어서 학습·서비스 전처리가 같다
  5. 칸마다 진짜 측정값이 있었는지(real_*)를 남긴다. 채점은 real_*가 True인 칸에서만 한다

결과: data/grid_5min.csv.gz (공간, 칸 시작 시각, co2·temperature·humidity(채운 값),
      real_co2 등(진짜 값 여부), n_co2 등(칸마다 값을 낸 센서 수))

사용법:
    python resample.py
"""

# 수정 기록
# - 2026-10-22 처음 작성 (5분 칸, 실습실 4개 센서 중앙값, 빈칸 길이 표)
# - 2026-10-22 4개 센서 중앙값과 전체 센서(복도 제외) 중앙값 차이 비교 추가 (센서 구성 결정용)
# - 2026-10-22 1시간 넘는 빈칸의 시작·끝 시각 목록 추가 (긴 끊김 원인 확인용)
# - 2026-10-22 빈칸 15분(3칸)까지 앞 값 채우기, real_* 칸 추가 (지원 결정: 4개 센서 확정, 15분 채우기)
# - 2026-10-22 채우기를 공간 값이 아니라 센서마다 먼저 하도록 변경 (칸마다 센서 조합이 바뀌어 중앙값이 출렁이던 문제. 기준선 표에서 5분 뒤 오차 > 30분 뒤 오차로 발견)

import pandas as pd

from clean import START, clean
from extremes import read_cache

BIN = "5min"
BASE_DEVICES = {                     # 실습실에 2025-09-03부터 계속 있던 센서
    "24e124126d152590",              # 전방 좌측
    "24e124126d152862",              # 후방 오른쪽
    "24e124128c067999",              # 후면 오른쪽
    "24e124128c140101",              # 전방 우측
}
MEASUREMENTS = ["co2", "temperature", "humidity"]
FILL_LIMIT = 3                       # 앞 값으로 채우는 최대 칸 수 (3칸 = 15분)
GAP_BUCKETS = [                      # (이름, 최소 칸 수, 최대 칸 수) 5분 칸 기준
    ("5분", 1, 1), ("10분", 2, 2), ("15분", 3, 3), ("20~30분", 4, 6),
    ("35~60분", 7, 12), ("1~3시간", 13, 36), ("3시간~1일", 37, 288), ("1일 넘게", 289, 10**9),
]


def to_grid(kept):
    """센서마다 5분 칸 평균 → 센서마다 15분까지 앞 값 채우기 → 공간 값(중앙값).

    채우기를 공간 값이 아니라 센서마다 먼저 하는 이유: 센서마다 보고 주기(1·2·10분)가 달라
    칸마다 값을 낸 센서 조합이 바뀐다. 센서끼리 100ppm쯤 차이가 나서, 조합이 바뀔 때마다
    중앙값이 출렁인다(2026-10-22 기준선 표에서 5분 뒤 오차 > 30분 뒤 오차로 드러남).
    센서마다 먼저 채우면 칸마다 같은 센서 조합으로 중앙값을 낸다.
    """
    df = kept[(kept["location"] == "회의실") | kept["device_id"].isin(BASE_DEVICES)].copy()
    df["bin"] = df["_time"].dt.floor(BIN)
    per_sensor = df.groupby(["location", "_measurement", "device_id", "bin"])["_value"].mean()

    full = pd.date_range(START, df["bin"].max(), freq=BIN)
    tables = []
    for loc in ["실습실", "회의실"]:
        t = pd.DataFrame(index=pd.Index(full, name="bin"))
        for m in MEASUREMENTS:
            wide = per_sensor.loc[(loc, m)].unstack("device_id").reindex(full)   # 칸 × 센서
            real = wide.notna().any(axis=1)                                     # 진짜 측정이 하나라도 있는 칸
            filled = wide.ffill(limit=FILL_LIMIT)
            t[m] = filled.median(axis=1)
            t["real_" + m] = real
            t["n_" + m] = filled.notna().sum(axis=1)
        t.insert(0, "location", loc)
        tables.append(t.reset_index())
    return pd.concat(tables, ignore_index=True)


def gap_table(grid, before_fill=False):
    """before_fill=True면 진짜 측정이 없는 칸(real_*가 False)을, 아니면 채운 뒤에도 빈 칸을 센다."""
    rows = []
    for loc, g in grid.groupby("location"):
        for m in MEASUREMENTS:
            missing = (~g["real_" + m] if before_fill else g[m].isna()).to_numpy()
            runs, n = [], 0
            for x in missing:
                if x:
                    n += 1
                elif n:
                    runs.append(n)
                    n = 0
            if n:
                runs.append(n)
            runs = pd.Series(runs, dtype=int)
            row = {"location": loc, "measurement": m,
                   "missing_rate_%": round(100 * missing.mean(), 1)}
            for name, lo, hi in GAP_BUCKETS:
                r = runs[(runs >= lo) & (runs <= hi)]
                row[name] = f"{len(r)}회/{r.sum() * 5 / 60:.1f}시간"
            rows.append(row)
    return pd.DataFrame(rows)


def long_gaps(grid, min_bins=12):
    """CO₂ 기준으로 min_bins칸(기본 1시간) 넘게 빈 구간의 시작·끝을 공간별로 보여 준다."""
    rows = []
    for loc, g in grid.groupby("location"):
        g = g.sort_values("bin")
        missing = ~g["real_co2"]
        run_id = (missing != missing.shift()).cumsum()
        for _, r in g[missing].groupby(run_id[missing]):
            if len(r) >= min_bins:
                rows.append({"location": loc,
                             "start": r["bin"].iloc[0].strftime("%Y-%m-%d %a %H:%M"),
                             "end": (r["bin"].iloc[-1] + pd.Timedelta(BIN)).strftime("%Y-%m-%d %a %H:%M"),
                             "hours": round(len(r) * 5 / 60, 1)})
    return pd.DataFrame(rows)


def compare_sensor_sets(kept, since="2026-08-10"):
    """새 센서가 붙은 뒤 기간에서, 4개 센서 중앙값과 전체 센서 중앙값이 얼마나 다른지 본다."""
    df = kept[(kept["location"] == "실습실") & (kept["_time"] >= pd.Timestamp(since, tz="Asia/Seoul"))].copy()
    df["bin"] = df["_time"].dt.floor(BIN)
    per_sensor = df.groupby(["_measurement", "device_id", "bin"])["_value"].mean().reset_index()
    rows = []
    for m in MEASUREMENTS:
        x = per_sensor[per_sensor["_measurement"] == m]
        base = x[x["device_id"].isin(BASE_DEVICES)].groupby("bin")["_value"].median()
        every = x.groupby("bin")["_value"].median()
        diff = (every - base).dropna()
        rows.append({"measurement": m, "sensors_all": x["device_id"].nunique(),
                     "mean_diff(all-4)": round(diff.mean(), 2), "mean_abs_diff": round(diff.abs().mean(), 2),
                     "p95_abs_diff": round(diff.abs().quantile(0.95), 2)})
    return pd.DataFrame(rows)


if __name__ == "__main__":
    kept, _ = clean(read_cache())
    grid = to_grid(kept)
    grid.to_csv("data/grid_5min.csv.gz", index=False)
    print(f"5분 칸 {len(grid) // 2:,}개 × 공간 2개 → data/grid_5min.csv.gz\n")

    pd.set_option("display.width", 250)
    print("== 채우기 전: 진짜 측정이 없는 칸의 길이별 횟수/합계 시간 (missing_rate = 빈칸 비율) ==")
    print(gap_table(grid, before_fill=True).to_string(index=False))
    print(f"\n== 센서마다 {FILL_LIMIT * 5}분까지 채운 뒤: 빈칸 비율 ==")
    print(gap_table(grid)[["location", "measurement", "missing_rate_%"]].to_string(index=False))
    print("\n== CO₂ 1시간 넘는 빈칸 ==")
    print(long_gaps(grid).to_string(index=False))

    print(f"\n== 실습실 2026-08-10 이후: 전체 센서 중앙값 - 4개 센서 중앙값 (같은 5분 칸끼리) ==")
    print(compare_sensor_sets(kept).to_string(index=False))
