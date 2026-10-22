"""aip-1 InfluxDB(jiwon 버킷)에서 하루 치 데이터를 읽어 표로 보여 준다. 읽기만 한다.

사용법 (Mac 터미널, 가상환경을 켠 뒤):
    export INFLUX_TOKEN=...        # jiwon 버킷 토큰. 이 창에서만 쓰이고 저장되지 않는다
    python load_day.py 2026-10-20  # 날짜는 KST 기준 하루
"""

# 수정 기록
# - 2026-10-22 처음 작성
# - 2026-10-22 _time을 format="ISO8601"로 읽음 (소수점 초가 있는 시각과 없는 시각이 섞여 나던 오류)
# - 2026-10-22 빈 'Unnamed' 칸 제거, DB 대기 시간 60초 → 300초 (한 달 치 읽기용)
# - 2026-10-22 결과가 비었을 때 빈 표 돌려주기, 태그 칸을 글자로 읽기(TAG_TYPES, DtypeWarning 제거)

import io
import json
import os
import sys
import urllib.request
from datetime import datetime, timedelta, timezone

import pandas as pd

URL = "http://100.98.23.5:8086"   # aip-1 Tailscale 주소
ORG = "aip-1"
BUCKET = "jiwon"
KST = timezone(timedelta(hours=9))
TAG_TYPES = {"device_id": str, "location": str, "point": str}   # 태그는 항상 글자로 읽는다


def query(flux):
    """Flux 쿼리를 보내고 결과 CSV를 pandas 표(DataFrame)로 돌려준다."""
    token = os.environ.get("INFLUX_TOKEN")
    if not token:
        sys.exit("INFLUX_TOKEN 환경변수가 없어요. export INFLUX_TOKEN=... 을 먼저 입력하세요.")
    body = json.dumps({"query": flux, "dialect": {"header": True, "annotations": []}}).encode()
    req = urllib.request.Request(
        f"{URL}/api/v2/query?org={ORG}",
        data=body,
        headers={
            "Authorization": f"Token {token}",
            "Content-Type": "application/json",
            "Accept": "application/csv",
        },
    )
    with urllib.request.urlopen(req, timeout=300) as resp:
        text = resp.read().decode()
    if not text.strip():   # 그 기간에 값이 하나도 없을 때
        return pd.DataFrame(columns=["_time", "_value", "_measurement", "location", "device_id", "point"])
    return pd.read_csv(io.StringIO(text), dtype=TAG_TYPES)


def load(start, stop):
    """start~stop 사이 co2·온도·습도 원본 값을 한 표로 읽는다."""
    flux = f'''
from(bucket: "{BUCKET}")
  |> range(start: {start.isoformat()}, stop: {stop.isoformat()})
  |> filter(fn: (r) => r._measurement == "co2" or r._measurement == "temperature" or r._measurement == "humidity")
  |> keep(columns: ["_time", "_value", "_measurement", "location", "device_id", "point"])
  |> group()
'''
    df = query(flux)
    df = df.drop(columns=[c for c in df.columns if c in ("result", "table") or c.startswith("Unnamed")])
    df["_time"] = pd.to_datetime(df["_time"], utc=True, format="ISO8601").dt.tz_convert("Asia/Seoul")
    return df.sort_values("_time")


if __name__ == "__main__":
    day = datetime.strptime(sys.argv[1], "%Y-%m-%d").replace(tzinfo=KST)
    df = load(day, day + timedelta(days=1))

    print(f"{sys.argv[1]} (KST) 전체 {len(df):,}건\n")
    print("== 공간·항목·센서별 건수, 최솟값, 최댓값 ==")
    summary = df.groupby(["location", "_measurement", "device_id"], dropna=False)["_value"].agg(["count", "min", "max"])
    print(summary.to_string())
    print("\n== 처음 10줄 ==")
    print(df.head(10).to_string(index=False))
