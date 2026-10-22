"""전체 기간(2025-08 ~ 지금)을 한 달씩 읽어, 센서별 값 범위와 재전송 중복을 센다. 읽기만 한다.

- 읽은 원본은 data/raw/YYYY-MM.csv.gz 로 Mac에 저장해 둔다(다음 분석부터는 DB를 다시 안 읽어도 됨).
  이미 있는 달은 다시 읽지 않는다. 이번 달만 매번 새로 읽는다.
- 결과 표는 화면에 보이고 data/scan_summary.csv 로도 저장된다.

사용법 (load_day.py와 같은 폴더, 가상환경 켜고 INFLUX_TOKEN 넣은 뒤):
    python scan_all.py
"""

# 수정 기록
# - 2026-10-22 처음 작성
# - 2026-10-22 캐시 파일을 읽을 때 태그 칸을 글자로 읽기(TAG_TYPES, DtypeWarning 제거)

import os
from datetime import datetime, timedelta

import pandas as pd

from load_day import KST, TAG_TYPES, load

FIRST_MONTH = datetime(2025, 8, 1, tzinfo=KST)
RAW_DIR = os.path.join("data", "raw")
DUP_WINDOW = pd.Timedelta(seconds=1)   # 같은 센서·항목·값이 1초 안에 다시 오면 재전송으로 본다


def month_starts():
    m = FIRST_MONTH
    now = datetime.now(KST)
    while m < now:
        yield m
        m = (m + timedelta(days=32)).replace(day=1)


def read_month(start):
    """한 달 치를 캐시에서 읽거나, 없으면 DB에서 읽어 캐시에 저장한다."""
    path = os.path.join(RAW_DIR, start.strftime("%Y-%m") + ".csv.gz")
    this_month = start.strftime("%Y-%m") == datetime.now(KST).strftime("%Y-%m")
    if os.path.exists(path) and not this_month:
        df = pd.read_csv(path, dtype=TAG_TYPES)
        df["_time"] = pd.to_datetime(df["_time"], utc=True, format="ISO8601").dt.tz_convert("Asia/Seoul")
        return df
    stop = (start + timedelta(days=32)).replace(day=1)
    df = load(start, stop)
    df.to_csv(path, index=False)
    return df


def mark_duplicates(df):
    """바로 앞 기록과 센서·항목·값이 같고 1초 안이면 True."""
    df = df.sort_values(["location", "_measurement", "device_id", "_time"])
    keys = ["location", "_measurement", "device_id"]
    prev_time = df.groupby(keys, dropna=False)["_time"].shift()
    prev_value = df.groupby(keys, dropna=False)["_value"].shift()
    df["dup"] = ((df["_time"] - prev_time) < DUP_WINDOW) & (df["_value"] == prev_value)
    return df


if __name__ == "__main__":
    os.makedirs(RAW_DIR, exist_ok=True)
    parts = []
    for start in month_starts():
        df = read_month(start)
        print(f"{start:%Y-%m}: {len(df):,}건")
        parts.append(df)
    df = mark_duplicates(pd.concat(parts, ignore_index=True))

    keys = ["location", "_measurement", "device_id"]
    g = df.groupby(keys, dropna=False)
    summary = pd.DataFrame({
        "point": g["point"].agg(lambda s: s.dropna().iloc[-1] if s.notna().any() else ""),
        "first": g["_time"].min().dt.strftime("%Y-%m-%d"),
        "last": g["_time"].max().dt.strftime("%Y-%m-%d"),
        "count": g.size(),
        "dup": g["dup"].sum(),
        "min": g["_value"].min(),
        "p01": g["_value"].quantile(0.01),
        "median": g["_value"].median(),
        "p99": g["_value"].quantile(0.99),
        "max": g["_value"].max(),
        "le_0": g["_value"].agg(lambda s: int((s <= 0).sum())),
    })
    pd.set_option("display.width", 200)
    print("\n== 센서별 전체 기간 요약 ==")
    print("dup = 1초 안 재전송 건수, p01/p99 = 하위·상위 1% 값, le_0 = 0 이하 값 건수")
    print(summary.to_string())
    summary.to_csv(os.path.join("data", "scan_summary.csv"))
    print("\n저장: data/scan_summary.csv")
