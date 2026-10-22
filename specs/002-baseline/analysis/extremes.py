"""높은 CO₂(기본 3,000ppm 초과)와 추운 실내(기본 10℃ 미만)가 언제, 얼마나 오래 있었는지 사건 단위로 보여 준다.

scan_all.py가 저장한 data/raw/*.csv.gz 만 읽는다(DB 접속 없음, 토큰 필요 없음).
같은 센서에서 기준을 넘은 기록끼리 30분 안에 이어지면 한 사건으로 묶는다.

사용법:
    python extremes.py
"""

# 수정 기록
# - 2026-10-22 처음 작성

import glob

import pandas as pd

from load_day import TAG_TYPES

CO2_HIGH = 3000
TEMP_LOW = 10
JOIN_GAP = pd.Timedelta(minutes=30)


def read_cache():
    parts = [pd.read_csv(p, dtype=TAG_TYPES) for p in sorted(glob.glob("data/raw/*.csv.gz"))]
    df = pd.concat(parts, ignore_index=True)
    df["_time"] = pd.to_datetime(df["_time"], utc=True, format="ISO8601").dt.tz_convert("Asia/Seoul")
    return df


def events(df, measurement, condition):
    """condition을 만족하는 기록을 센서별로 묶어 사건 표를 만든다."""
    sel = df[(df["_measurement"] == measurement) & condition(df["_value"])]
    sel = sel.sort_values(["location", "device_id", "_time"])
    rows = []
    for (loc, dev), g in sel.groupby(["location", "device_id"], dropna=False):
        event_id = (g["_time"].diff() > JOIN_GAP).cumsum()
        for _, e in g.groupby(event_id):
            rows.append({
                "location": loc,
                "point": e["point"].dropna().iloc[-1] if e["point"].notna().any() else "",
                "device_id": dev,
                "start": e["_time"].min().strftime("%Y-%m-%d %a %H:%M"),
                "minutes": round((e["_time"].max() - e["_time"].min()).total_seconds() / 60),
                "n": len(e),
                "min": e["_value"].min(),
                "max": e["_value"].max(),
            })
    return pd.DataFrame(rows)


if __name__ == "__main__":
    pd.set_option("display.width", 200)
    pd.set_option("display.max_rows", 500)
    df = read_cache()

    high = events(df, "co2", lambda v: v > CO2_HIGH)
    print(f"== CO₂ {CO2_HIGH}ppm 초과 사건: {len(high)}건 (minutes = 첫 기록~마지막 기록, n = 기록 수) ==")
    print(high.to_string(index=False))
    high.to_csv("data/co2_high_events.csv", index=False)

    cold = df[(df["_measurement"] == "temperature") & (df["_value"] < TEMP_LOW)]
    print(f"\n== 온도 {TEMP_LOW}℃ 미만 기록이 있는 날 (공간·날짜별 건수, 최저) ==")
    by_day = cold.groupby(["location", cold["_time"].dt.strftime("%Y-%m-%d %a")])["_value"].agg(["count", "min"])
    print(by_day.to_string())
