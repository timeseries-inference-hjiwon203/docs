#!/usr/bin/env python3
"""강사 InfluxDB(iot-bucket)에서 실습실·회의실의 co2/temperature/humidity를 읽어
aip-1의 내 InfluxDB 버킷에 복사한다.

- 설정: config.json (장소·항목·주소). 형식이 바뀌면 이 파일만 고친다.
- 토큰: 환경 변수 STAFF_TOKEN(읽기), MY_TOKEN(쓰기). 파일에 적지 않는다.
- 진행 상황: state.json에 "어디까지 복사했는지" 시각을 저장한다.
  다음 실행은 그 시각보다 overlap_minutes 앞에서부터 다시 읽는다.
  같은 (항목, 태그, 시각) 점은 덮어써지므로 겹쳐 읽어도 중복이 생기지 않는다.

사용법:
  python3 sync.py            # 한 번 실행 (timer가 1분마다 부른다)
  python3 sync.py --dry-run  # 읽기만 하고 쓰지 않음, 앞 5줄 출력
"""
import csv
import io
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))


def log(msg):
    # systemd가 표준 출력을 journal에 저장한다 → journalctl -u collector 로 본다
    print(msg, flush=True)


def load_json(path, default=None):
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def parse_utc(text):
    # "2026-10-21T00:00:00Z" → datetime
    return datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def fmt_utc(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def http_post(url, token, body, content_type, accept=None):
    req = urllib.request.Request(url, data=body.encode("utf-8"), method="POST")
    req.add_header("Authorization", "Token " + token)
    req.add_header("Content-Type", content_type)
    if accept:
        req.add_header("Accept", accept)
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read().decode("utf-8")


def flux_list(values):
    return "[" + ", ".join('"' + v + '"' for v in values) + "]"


def build_query(cfg, start, stop):
    src = cfg["source"]
    tags = cfg["tags"]
    return f"""
from(bucket: "{src['bucket']}")
  |> range(start: {fmt_utc(start)}, stop: {fmt_utc(stop)})
  |> filter(fn: (r) => contains(value: r._measurement, set: {flux_list(list(cfg['measurements']))}))
  |> filter(fn: (r) => exists r.location and contains(value: r.location, set: {flux_list(cfg['locations'])}))
  |> filter(fn: (r) => r._field == "{src['field']}")
  |> map(fn: (r) => ({{r with _ns: int(v: r._time), _value: float(v: r._value)}}))
  |> keep(columns: {flux_list(["_ns", "_value", "_measurement"] + tags)})
"""


def read_rows(csv_text):
    # InfluxDB CSV는 표마다 머리줄이 다시 나오고, 표 사이에 빈 줄이 있다.
    header = None
    for row in csv.reader(io.StringIO(csv_text)):
        if not row or not any(row):
            header = None
            continue
        if row[0].startswith("#"):
            continue
        if header is None:
            header = row
            continue
        yield dict(zip(header, row))


def escape_tag(text):
    # 라인 프로토콜에서 쉼표·등호·공백은 앞에 \ 를 붙인다
    return text.replace("\\", "\\\\").replace(",", "\\,").replace("=", "\\=").replace(" ", "\\ ")


def to_line(cfg, row):
    name = cfg["measurements"][row["_measurement"]]  # 원본 이름 → 내 DB 이름
    tag_part = "".join(
        f",{t}={escape_tag(row[t])}" for t in sorted(cfg["tags"]) if row.get(t)
    )
    value = float(row["_value"])
    return f"{escape_tag(name)}{tag_part} value={value} {row['_ns']}", int(row["_ns"])


def write_lines(cfg, token, lines):
    tgt = cfg["target"]
    qs = urllib.parse.urlencode({"org": tgt["org"], "bucket": tgt["bucket"], "precision": "ns"})
    url = tgt["url"].rstrip("/") + "/api/v2/write?" + qs
    batch = cfg.get("write_batch", 5000)
    for i in range(0, len(lines), batch):
        http_post(url, token, "\n".join(lines[i:i + batch]), "text/plain; charset=utf-8")


def sync_window(cfg, staff_token, my_token, start, stop, dry_run):
    src = cfg["source"]
    url = src["url"].rstrip("/") + "/api/v2/query?" + urllib.parse.urlencode({"orgID": src["org_id"]})
    text = http_post(url, staff_token, build_query(cfg, start, stop),
                     "application/vnd.flux", "application/csv")
    lines, newest, counts = [], None, {}
    for row in read_rows(text):
        try:
            line, ns = to_line(cfg, row)
        except (KeyError, ValueError) as e:
            log(f"  건너뜀(형식 오류 {e!r}): {row}")
            continue
        lines.append(line)
        newest = ns if newest is None or ns > newest else newest
        key = f"{row.get('location', '?')}/{row['_measurement']}"
        counts[key] = counts.get(key, 0) + 1
    if dry_run:
        for line in lines[:5]:
            log("  " + line)
    elif lines:
        write_lines(cfg, my_token, lines)
    summary = ", ".join(f"{k}={v}" for k, v in sorted(counts.items())) or "새 값 없음"
    log(f"{fmt_utc(start)} ~ {fmt_utc(stop)}: {len(lines)}건 ({summary})")
    return newest


def main():
    dry_run = "--dry-run" in sys.argv
    cfg = load_json(os.path.join(HERE, "config.json"))
    state_path = os.path.join(HERE, cfg.get("state_file", "state.json"))
    staff_token = os.environ.get("STAFF_TOKEN")
    my_token = os.environ.get("MY_TOKEN")
    if not staff_token or (not my_token and not dry_run):
        log("환경 변수 STAFF_TOKEN / MY_TOKEN 이 비어 있어요.")
        return 2

    state = load_json(state_path, {})
    now = datetime.now(timezone.utc).replace(microsecond=0)
    if dry_run:
        start = now - timedelta(minutes=30)  # 시험 실행은 최근 30분만 본다
    elif "last_time" in state:
        start = parse_utc(state["last_time"]) - timedelta(minutes=cfg["overlap_minutes"])
    else:
        start = parse_utc(cfg["backfill_start"])  # 처음 실행: 과거 데이터부터 채움

    chunk = timedelta(hours=cfg.get("chunk_hours", 24))
    while start < now:
        stop = min(start + chunk, now)
        try:
            sync_window(cfg, staff_token, my_token, start, stop, dry_run)
        except (urllib.error.URLError, OSError) as e:
            # 강사 DB나 내 DB가 잠깐 안 될 때: state를 그대로 두고 끝낸다.
            # 다음 실행(1분 뒤)이 같은 구간부터 다시 시도한다.
            body = e.read().decode("utf-8", "replace")[:300] if isinstance(e, urllib.error.HTTPError) else ""
            log(f"실패 {fmt_utc(start)} ~ {fmt_utc(stop)}: {e} {body}")
            return 1
        if not dry_run:
            with open(state_path, "w", encoding="utf-8") as f:
                json.dump({"last_time": fmt_utc(stop)}, f)
        if dry_run:
            break
        start = stop
    return 0


if __name__ == "__main__":
    sys.exit(main())
