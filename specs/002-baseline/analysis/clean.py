"""정제 규칙. 과제 8 서비스(Jetson)에서도 같은 규칙을 쓰도록 이 파일 하나에 모아 둔다.

규칙(2026-10-22 지원 결정):
  1. 2025-09-03 이전 데이터는 쓰지 않는다 (device_id 없음, 약 1주뿐)
  2. 복도 센서(24e124136d151523)는 실습실 값에서 뺀다
  3. 재전송 중복: 같은 센서·항목·값이 1초 안에 다시 오면 뒤의 것을 버린다
  4. 물리적으로 불가능한 값: CO₂ 350ppm 미만·10,000ppm 이상, 습도 0~100% 밖, 온도 0℃ 이하는 버린다
  5. 같은 센서가 같은 시각에 보낸 기록 중 하나라도 4번에 걸렸으면, 그 시각의 그 센서 기록은 전부 버린다
     (센서는 CO₂·온도·습도를 한 번에 보낸다. 하나가 깨졌으면 나머지도 믿기 어렵다)

사용법:
    python clean.py      # data/raw 캐시에 규칙을 적용하고, 규칙별로 버린 건수를 보여 준다
"""

# 수정 기록
# - 2026-10-22 처음 작성 (규칙 1~4, CO₂ 위쪽 한계는 미정으로 비워 둠)
# - 2026-10-22 CO₂ 위쪽 한계 5,000ppm 추가, 규칙 5(같은 시각 기록 함께 버리기) 추가 (지원 결정)
# - 2026-10-22 CO₂ 위쪽 한계 5,000 → 10,000 이상 제거로 변경 (회의실 2025-09-18 7,029까지 실제로 오른 것 확인, 지원 결정)

import pandas as pd

START = pd.Timestamp("2025-09-03", tz="Asia/Seoul")
EXCLUDE_DEVICES = {"24e124136d151523"}          # 복도
DUP_WINDOW = pd.Timedelta(seconds=1)
VALID = {                                       # 항목별 "믿을 수 있는 값" 조건. 조건 밖은 버린다
    "co2": lambda v: (v >= 350) & (v < 10000),  # 10000(측정 한계)·65535(오류 코드) 제거. 7,000대는 실제 값
    "humidity": lambda v: (v >= 0) & (v <= 100),
    "temperature": lambda v: v > 0,
}


def clean(df):
    """원본 표를 받아 (정제된 표, 규칙별 버린 건수 표)를 돌려준다."""
    df = df.copy()
    df["reason"] = ""

    df.loc[df["_time"] < START, "reason"] = "1_before_start"
    df.loc[(df["reason"] == "") & df["device_id"].isin(EXCLUDE_DEVICES), "reason"] = "2_corridor"

    keys = ["location", "_measurement", "device_id"]
    df = df.sort_values(keys + ["_time"])
    prev_time = df.groupby(keys, dropna=False)["_time"].shift()
    prev_value = df.groupby(keys, dropna=False)["_value"].shift()
    dup = ((df["_time"] - prev_time) < DUP_WINDOW) & (df["_value"] == prev_value)
    df.loc[(df["reason"] == "") & dup, "reason"] = "3_resend"

    for m, is_valid in VALID.items():
        is_m = (df["reason"] == "") & (df["_measurement"] == m)
        df.loc[is_m & ~is_valid(df["_value"]), "reason"] = "4_out_of_range"

    broken = df.loc[df["reason"] == "4_out_of_range", ["device_id", "_time"]].drop_duplicates()
    same_time = df.set_index(["device_id", "_time"]).index.isin(pd.MultiIndex.from_frame(broken))
    df.loc[(df["reason"] == "") & same_time, "reason"] = "5_same_time"

    report = (df.groupby(["location", "_measurement", "reason"]).size()
                .unstack("reason", fill_value=0).rename(columns={"": "kept"}))
    kept = df[df["reason"] == ""].drop(columns="reason").sort_values("_time")
    return kept, report


if __name__ == "__main__":
    from extremes import read_cache

    raw = read_cache()
    kept, report = clean(raw)
    pd.set_option("display.width", 200)
    print(f"원본 {len(raw):,}건 → 남은 {len(kept):,}건\n")
    print("== 공간·항목별, 규칙별 건수 (kept = 남은 것) ==")
    print(report.to_string())
    report.to_csv("data/clean_report.csv")
    print("\n저장: data/clean_report.csv")
