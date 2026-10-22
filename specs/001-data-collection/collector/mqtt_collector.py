#!/usr/bin/env python3
"""MQTT 브로커에서 센서 값을 바로 받아 aip-1의 내 InfluxDB 버킷에 저장한다.

- 받기: mosquitto_sub(이미 설치된 명령)을 실행해서 메시지를 한 줄씩 읽는다.
  비밀번호는 명령줄에 쓰지 않고(다른 사용자가 ps로 볼 수 있음),
  권한 600 설정 파일로 넘긴다.
- 시각: 메시지의 time(게이트웨이 시계, 몇 분 빠를 수 있음)이 아니라
  rxInfo[].nsTime(네트워크 서버가 받은 시각) 중 가장 이른 값을 쓴다.
  그래도 지금보다 future_seconds 넘게 미래면 로그를 남기고 지금 시각으로 저장한다.
- 중복: 게이트웨이 여러 대가 같은 업링크를 따로 보내므로
  (devEui, fCnt)가 같은 메시지는 한 번만 저장한다.
- 빈 구간: 시작할 때 마지막으로 저장한 시각부터 지금까지를
  강사 DB에서 가져와 채운다(sync.py와 같은 조회). 강사 DB는 같은 업링크를
  몇 ms 차이로 두 번 저장한 경우가 있어서 1초 안의 값은 하나만 남긴다.
- 장애: 브로커가 끊기거나 메시지가 no_message_minutes 동안 없거나
  내 DB에 쓰지 못하면 종료한다. systemd가 다시 실행하고, 그때 빈 구간을 채운다.

사용법:
  python3 mqtt_collector.py            # 계속 실행 (systemd 서비스)
  python3 mqtt_collector.py --dry-run  # 쓰지 않고 받은 값만 출력, 빈 구간 채우기 생략
환경 변수: MQTT_PW, STAFF_TOKEN, MY_TOKEN (.env)
"""
import json
import os
import select
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
from datetime import datetime, timedelta, timezone

from status import load_env_file
from sync import HERE, build_query, escape_tag, fmt_utc, http_post, load_json, log, read_rows, to_line, write_lines

NS = 1_000_000_000


def parse_rfc3339_ns(text):
    # "2026-10-22T02:09:21.736683374+00:00" 또는 "...Z" → 1970년부터의 나노초
    text = text.replace("Z", "+00:00")
    main, offset = text[:-6], text[-6:]
    frac = ""
    if "." in main:
        main, frac = main.split(".", 1)
    dt = datetime.fromisoformat(main + offset)
    return int(dt.timestamp()) * NS + int((frac + "000000000")[:9])


def ns_to_text(ns):
    return datetime.fromtimestamp(ns // NS, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def message_to_lines(cfg, msg, now_ns):
    """메시지 하나 → ([(내 DB 항목 이름, 라인 프로토콜 줄)], 저장 시각 ns). 대상이 아니면 ([], None)."""
    m = cfg["mqtt"]
    info = msg.get("deviceInfo", {})
    tags = dict(info.get("tags", {}))
    tags["device_id"] = info.get("devEui") or msg.get("devEui", "")
    if tags.get("location") not in cfg["locations"]:
        return [], None

    ns_times = [parse_rfc3339_ns(rx["nsTime"]) for rx in msg.get("rxInfo", []) if rx.get("nsTime")]
    if ns_times:
        ns = min(ns_times)
    else:
        log(f"  nsTime 없음, 받은 시각으로 저장: {tags['device_id']} fCnt={msg.get('fCnt')}")
        ns = now_ns
    if ns > now_ns + m.get("future_seconds", 60) * NS:
        log(f"  미래 시각 {ns_to_text(ns)} → 지금 시각으로 저장: {tags['device_id']} fCnt={msg.get('fCnt')}")
        ns = now_ns

    tag_part = "".join(f",{t}={escape_tag(tags[t])}" for t in sorted(cfg["tags"]) if tags.get(t))
    lines = []
    for key, name in m["measurements"].items():  # 메시지 object 키 → 내 DB 이름
        value = msg.get("object", {}).get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            lines.append((name, f"{escape_tag(name)}{tag_part} value={float(value)} {ns}"))
    return lines, ns


def fill_gap(cfg, staff_token, my_token, start, stop):
    """강사 DB에서 start~stop 구간을 가져와 쓴다. 1초 안의 같은 센서 값은 하나만.
    센서별 마지막 시각 {(내 DB 항목 이름, device_id): ns}을 돌려준다."""
    src = cfg["source"]
    url = src["url"].rstrip("/") + "/api/v2/query?" + urllib.parse.urlencode({"orgID": src["org_id"]})
    rows = []
    chunk = timedelta(hours=cfg.get("chunk_hours", 24))
    t = start
    while t < stop:
        end = min(t + chunk, stop)
        text = http_post(url, staff_token, build_query(cfg, t, end), "application/vnd.flux", "application/csv")
        rows.extend(r for r in read_rows(text) if r.get("_measurement") in cfg["measurements"])
        t = end
    rows.sort(key=lambda r: (r["_measurement"], r.get("device_id", ""), int(r["_ns"])))

    lines, last, dropped = [], {}, 0
    for r in rows:
        key = (r["_measurement"], r.get("device_id", ""))
        ns = int(r["_ns"])
        if key in last and ns - last[key] < NS:
            dropped += 1
            continue
        last[key] = ns
        lines.append(to_line(cfg, r)[0])
    if lines:
        write_lines(cfg, my_token, lines)
    log(f"빈 구간 채움 {fmt_utc(start)} ~ {fmt_utc(stop)}: {len(lines)}건 (1초 안 중복 {dropped}건 제외)")
    return {(cfg["measurements"][k[0]], k[1]): ns for k, ns in last.items()}


def start_subscriber(cfg, password):
    """mosquitto_sub 실행. 비밀번호는 권한 600 임시 설정 파일로 넘긴다."""
    m = cfg["mqtt"]
    conf_dir = tempfile.mkdtemp(prefix="mqtt-", dir=HERE)  # 권한 700 폴더
    conf = os.path.join(conf_dir, "mosquitto_sub")
    fd = os.open(conf, os.O_WRONLY | os.O_CREAT, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(f"-u {m['username']}\n-P {password}\n")
    cmd = ["mosquitto_sub", "-h", m["host"], "-p", str(m["port"]), "-t", m["topic"],
           "-q", "1", "-k", "60", "-i", m["client_id"]]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, env={**os.environ, "XDG_CONFIG_HOME": conf_dir})
    time.sleep(2)  # 설정 파일을 읽을 시간을 준 뒤 지운다
    os.remove(conf)
    os.rmdir(conf_dir)
    return proc


def read_messages(proc, timeout_s):
    """mosquitto_sub 출력에서 메시지(한 줄 JSON)를 하나씩 돌려준다.
    timeout_s 동안 아무것도 없거나 mosquitto_sub가 끝나면 멈춘다."""
    buf = b""
    fd = proc.stdout.fileno()
    while True:
        ready, _, _ = select.select([fd], [], [], timeout_s)
        if not ready:
            log(f"{timeout_s // 60}분 동안 메시지 없음")
            return
        chunk = os.read(fd, 65536)
        if not chunk:
            log(f"mosquitto_sub 종료 (코드 {proc.wait()})")
            return
        buf += chunk
        while b"\n" in buf:
            line, buf = buf.split(b"\n", 1)
            if line.strip():
                yield line


def save_state(path, ns):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"last_time": ns_to_text(ns), "last_ns": ns}, f)
    os.replace(tmp, path)


def main():
    dry_run = "--dry-run" in sys.argv
    cfg = load_json(os.path.join(HERE, "config.json"))
    load_env_file(os.path.join(HERE, ".env"))
    m = cfg["mqtt"]
    password, staff_token, my_token = (os.environ.get(k) for k in ("MQTT_PW", "STAFF_TOKEN", "MY_TOKEN"))
    if not password or (not dry_run and not (staff_token and my_token)):
        log("환경 변수 MQTT_PW / STAFF_TOKEN / MY_TOKEN 이 비어 있어요.")
        return 2

    state_path = os.path.join(HERE, m["state_file"])
    # 처음 실행이면 DB 복사(sync.py)가 멈춘 지점부터 이어서 채운다
    state = load_json(state_path) or load_json(os.path.join(HERE, cfg.get("state_file", "state.json")), {})

    proc = start_subscriber(cfg, password)
    if not dry_run and "last_time" in state:
        # 구독을 먼저 시작해 두고, 그 사이 빈 구간을 강사 DB에서 채운다
        start = datetime.strptime(state["last_time"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        if "last_ns" in state:  # MQTT로 마지막 저장한 값의 정확한 시각
            start = datetime.fromtimestamp(state["last_ns"] / NS, timezone.utc)
        stop = datetime.now(timezone.utc).replace(microsecond=0)
        try:
            filled = fill_gap(cfg, staff_token, my_token, start + timedelta(seconds=1), stop)
        except (urllib.error.URLError, OSError) as e:
            log(f"빈 구간 채우기 실패 (다음 재시작 때 다시 시도): {e}")
            proc.terminate()
            return 1
    else:
        filled = {}

    seen = {}  # (devEui, fCnt) → 받은 시각(초). 오래된 건 지운다
    newest = 0
    log(f"MQTT 구독 시작: {m['host']}:{m['port']} {m['topic']}")
    for raw in read_messages(proc, m.get("no_message_minutes", 10) * 60):
        now = time.time()
        try:
            msg = json.loads(raw)
        except ValueError:
            log(f"  JSON 아님, 건너뜀: {raw[:100]!r}")
            continue
        key = (msg.get("deviceInfo", {}).get("devEui"), msg.get("fCnt"))
        if key in seen:
            log(f"  중복 업링크 건너뜀: {key[0]} fCnt={key[1]}")
            continue
        seen[key] = now
        if len(seen) > 5000:
            seen = {k: v for k, v in seen.items() if now - v < 3600}

        pairs, ns = message_to_lines(cfg, msg, int(now * NS))
        # 빈 구간 채우기와 겹치는 첫 메시지: 강사 DB 값(시각이 수백 ms 다름)이 이미 있으면 건너뛴다
        dev = msg.get("deviceInfo", {}).get("devEui", "")
        lines = [line for name, line in pairs if abs(ns - filled.get((name, dev), -10 * NS)) >= 2 * NS]
        if not lines:
            continue
        if dry_run:
            for line in lines:
                log("  " + line)
            continue
        try:
            write_lines(cfg, my_token, lines)
        except (urllib.error.URLError, OSError) as e:
            log(f"내 DB 쓰기 실패: {e}")
            break
        if ns > newest:
            newest = ns
            save_state(state_path, ns)
        log(f"  {key[0]} fCnt={key[1]} {ns_to_text(ns)} {len(lines)}건")

    proc.terminate()
    return 1  # 여기까지 오면 끊긴 것. systemd가 다시 실행한다


if __name__ == "__main__":
    sys.exit(main())
