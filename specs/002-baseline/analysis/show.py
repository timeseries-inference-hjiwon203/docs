"""저장된 원본(data/raw)에서 한 공간·한 항목의 값을 시각 순서대로 보여 준다. 정제 전 값 그대로.

사용법:
    python show.py 회의실 co2 "2025-09-18 12:00" "2025-09-18 20:00"
"""

# 수정 기록
# - 2026-10-22 처음 작성 (회의실 2025-09-18 고농도 구간 확인용)

import sys

import pandas as pd

from extremes import read_cache

if __name__ == "__main__":
    location, measurement, start, stop = sys.argv[1:5]
    start = pd.Timestamp(start, tz="Asia/Seoul")
    stop = pd.Timestamp(stop, tz="Asia/Seoul")
    df = read_cache()
    sel = df[(df["location"] == location) & (df["_measurement"] == measurement)
             & (df["_time"] >= start) & (df["_time"] < stop)]
    pd.set_option("display.max_rows", 1000)
    print(sel[["_time", "device_id", "point", "_value"]].sort_values("_time").to_string(index=False))
