#!/usr/bin/env python3
"""내 버킷에 데이터가 잘 쌓이고 있는지 보여 주는 현황표 (과제 1 US3).

센서(장소·항목·device_id)마다:
  건수, 보고 주기, 마지막 값 시각, 커버율, 오래 빈 구간(시작~끝)

커버율 = 기간을 N분 칸으로 나눴을 때 값이 1개 이상 있는 칸의 비율.
센서마다 보고 주기가 달라서(1분, 2분, 10분) N은 센서마다
"그 센서의 보통 보고 간격(중앙값) × coverage_factor"로 정한다.
  예) 10분마다 보고하는 센서, factor 2 → 20분 칸

사용법:
  python3 status.py              # 최근 24시간
  python3 status.py --hours 168  # 최근 7일
"""
import math
import os
import sys
import urllib.parse
from datetime import datetime, timedelta, timezone

from sync import HERE, flux_list, http_post, load_json, read_rows


def load_env_file(path):
    # systemd용 .env 파일(이름=값)을 읽어 환경 변수에 없는 값만 채운다
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            if "=" in line and not line.startswith("#"):
                key, value = line.strip().split("=", 1)
                os.environ.setdefault(key, value)


def query(cfg, token, flux):
    tgt = cfg["target"]
    url = tgt["url"].rstrip("/") + "/api/v2/query?" + urllib.parse.urlencode({"org": tgt["org"]})
    return list(read_rows(http_post(url, token, flux, "application/vnd.flux", "application/csv")))


def short_time(text, minus_minutes=0):
    # "2026-10-21T06:52:33.123Z" → 이 컴퓨터 시간대(한국) "10-21 15:52"
    dt = datetime.fromisoformat(text[:19]).replace(tzinfo=timezone.utc).astimezone()
    return (dt - timedelta(minutes=minus_minutes)).strftime("%m-%d %H:%M")


def main():
    hours = int(sys.argv[sys.argv.index("--hours") + 1]) if "--hours" in sys.argv else 24
    cfg = load_json(os.path.join(HERE, "config.json"))
    load_env_file(os.path.join(HERE, ".env"))
    token = os.environ.get("MY_TOKEN")
    if not token:
        print("MY_TOKEN 이 없어요. .env 파일이나 환경 변수를 확인하세요.")
        return 2

    st = cfg.get("status", {})
    factor = st.get("coverage_factor", 2)
    gap_minutes = st.get("gap_minutes", 30)
    names = flux_list(list(cfg["measurements"].values()))
    print(f"기간: 최근 {hours}시간 / 커버율 칸 = 보고 주기 × {factor} / 빈 구간 기준: {gap_minutes}분 이상\n")

    for loc in cfg["locations"]:
        base = f"""
from(bucket: "{cfg['target']['bucket']}")
  |> range(start: -{hours}h)
  |> filter(fn: (r) => contains(value: r._measurement, set: {names}) and r.location == "{loc}" and r._field == "value")
  |> group(columns: ["_measurement", "device_id"])
"""
        stats = {}

        def put(rows, column, name):
            for r in rows:
                stats.setdefault((r["_measurement"], r.get("device_id", "")), {})[name] = r[column]

        put(query(cfg, token, base + "|> count()"), "_value", "count")
        put(query(cfg, token, base + "|> last()"), "_time", "last")
        put(query(cfg, token, base + """
  |> sort(columns: ["_time"])
  |> elapsed(unit: 1s)
  |> median(column: "elapsed")"""), "elapsed", "interval_s")
        gaps = query(cfg, token, base + f"""
  |> sort(columns: ["_time"])
  |> elapsed(unit: 1m)
  |> filter(fn: (r) => r.elapsed >= {gap_minutes})""")

        # 센서마다 칸 크기가 달라서 커버율은 센서별로 따로 묻는다
        for (meas, dev), s in stats.items():
            if "interval_s" not in s:
                continue
            interval_min = max(1, round(float(s["interval_s"]) / 60))
            window = math.ceil(interval_min * factor)
            s["interval"], s["window"] = interval_min, window
            dev_filter = f'r.device_id == "{dev}"' if dev else "not exists r.device_id"
            rows = query(cfg, token, base + f"""
  |> filter(fn: (r) => r._measurement == "{meas}" and {dev_filter})
  |> aggregateWindow(every: {window}m, fn: count, createEmpty: true)
  |> map(fn: (r) => ({{r with _value: if r._value > 0 then 1.0 else 0.0}}))
  |> mean()""")
            if rows:
                s["coverage"] = rows[0]["_value"]

        print(f"[{loc}]")
        print(f"  {'항목':<12}{'device_id':<18}{'건수':>6} {'주기':>4} {'칸':>4}  {'마지막(한국)':<12}{'커버율':>7}")
        for (meas, dev), s in sorted(stats.items()):
            cov = f"{float(s['coverage']) * 100:.1f}%" if "coverage" in s else "-"
            last = short_time(s["last"]) if "last" in s else "-"
            print(f"  {meas:<12}{dev or '(없음)':<18}{s.get('count', '0'):>6} "
                  f"{str(s.get('interval', '-')) + '분':>4} {str(s.get('window', '-')) + '분':>4}  {last:<12}{cov:>7}")
        for g in gaps:
            mins = int(g["elapsed"])
            print(f"  빈 구간: {g['_measurement']} {g.get('device_id') or '(없음)'} "
                  f"{short_time(g['_time'], mins)} ~ {short_time(g['_time'])} ({mins}분)")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
