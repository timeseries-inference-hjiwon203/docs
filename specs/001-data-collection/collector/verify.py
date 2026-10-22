#!/usr/bin/env python3
"""심화(B) 확인용: 강사 DB와 내 DB의 건수를 비교한다. 읽기만 한다.

- 같은 날의 건수가 양쪽에서 같으면, 매분 30분씩 겹쳐 다시 써도
  중복이 생기지 않았다는 증거가 된다 (T023).
- 내 DB 전체 건수는 저장 용량 추정(점 1개당 바이트)에 쓴다 (T022).

사용법:
  python3 verify.py 2026-10-20     # 그날(UTC 기준 하루) 건수 비교
  python3 verify.py --total        # 내 DB 전체 건수
"""
import os
import sys
import urllib.parse
from datetime import datetime, timedelta, timezone

from status import load_env_file
from sync import HERE, flux_list, http_post, load_json, read_rows


def count_rows(base_url, params, token, flux):
    url = base_url.rstrip("/") + "/api/v2/query?" + urllib.parse.urlencode(params)
    rows = read_rows(http_post(url, token, flux, "application/vnd.flux", "application/csv"))
    return {(r.get("location", ""), r["_measurement"]): int(r["_value"]) for r in rows}


def main():
    cfg = load_json(os.path.join(HERE, "config.json"))
    load_env_file(os.path.join(HERE, ".env"))
    src, tgt = cfg["source"], cfg["target"]
    staff, mine = os.environ.get("STAFF_TOKEN"), os.environ.get("MY_TOKEN")
    names = list(cfg["measurements"].values())

    if "--total" in sys.argv:
        # 전체를 한 번에 세면 Jetson에서 시간이 오래 걸려(60초 초과) 30일씩 나눠 센다
        start = datetime.strptime(cfg["backfill_start"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        totals = {}
        while start < now:
            stop = min(start + timedelta(days=30), now)
            flux = f"""
from(bucket: "{tgt['bucket']}")
  |> range(start: {start:%Y-%m-%dT%H:%M:%SZ}, stop: {stop:%Y-%m-%dT%H:%M:%SZ})
  |> filter(fn: (r) => contains(value: r._measurement, set: {flux_list(names)}))
  |> group(columns: ["location", "_measurement"])
  |> count()"""
            counts = count_rows(tgt["url"], {"org": tgt["org"]}, mine, flux)
            print(f"  {start:%Y-%m-%d} ~ {stop:%Y-%m-%d}: {sum(counts.values()):>9,}건", flush=True)
            for key, n in counts.items():
                totals[key] = totals.get(key, 0) + n
            start = stop
        print()
        for key, n in sorted(totals.items()):
            print(f"  {key[0]:<6} {key[1]:<12} {n:>10,}")
        print(f"  합계 {sum(totals.values()):,}건")
        return 0

    day = sys.argv[1] if len(sys.argv) > 1 else (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
    start = f"{day}T00:00:00Z"
    stop = (datetime.strptime(day, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%dT00:00:00Z")

    # 강사 DB: sync.py와 같은 조건(항목, 장소, field)으로 센다
    src_flux = f"""
from(bucket: "{src['bucket']}")
  |> range(start: {start}, stop: {stop})
  |> filter(fn: (r) => contains(value: r._measurement, set: {flux_list(list(cfg['measurements']))}))
  |> filter(fn: (r) => exists r.location and contains(value: r.location, set: {flux_list(cfg['locations'])}))
  |> filter(fn: (r) => r._field == "{src['field']}")
  |> group(columns: ["location", "_measurement"])
  |> count()"""
    my_flux = f"""
from(bucket: "{tgt['bucket']}")
  |> range(start: {start}, stop: {stop})
  |> filter(fn: (r) => contains(value: r._measurement, set: {flux_list(names)}))
  |> group(columns: ["location", "_measurement"])
  |> count()"""
    a = count_rows(src["url"], {"orgID": src["org_id"]}, staff, src_flux)
    a = {(loc, cfg["measurements"][m]): n for (loc, m), n in a.items()}  # 원본 이름 → 내 이름
    b = count_rows(tgt["url"], {"org": tgt["org"]}, mine, my_flux)

    print(f"{day} (UTC 하루) 건수 비교")
    print(f"  {'장소':<6}{'항목':<12}{'강사 DB':>9}{'내 DB':>9}  결과")
    for key in sorted(set(a) | set(b)):
        x, y = a.get(key, 0), b.get(key, 0)
        print(f"  {key[0]:<6}{key[1]:<12}{x:>9,}{y:>9,}  {'같음' if x == y else '다름'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
