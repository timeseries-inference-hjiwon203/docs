"""진단: 평일 시간대별 패턴, 수업 일정 → CO₂ 반응 시간, 일정과 안 맞는 날.

수업 일정(지원 확인): 공휴일을 뺀 평일 09:00~18:00, 점심 11:30~13:00.
회의실 예약 자료는 없어서 회의실은 패턴 그래프만 그린다.

하는 일
  1. 공간·항목마다 시간대별 평균 그래프 (수업일은 시기별로, 쉬는 날은 한 줄)
  2. 실습실 수업일마다: 아침 기준값, CO₂가 오르기 시작한 시각, 오전 최고 시각, 점심 최저 시각, 하루 변화 폭
  3. 일정과 안 맞는 날: 수업일인데 CO₂가 거의 안 오른 날, 쉬는 날인데 많이 오른 날

표와 반응 시간은 진짜 측정값(real_*)인 칸만 쓴다. 그래프는 15분까지 채운 값도 쓴다(회의실 지그재그 방지).

사용법:
    python patterns.py
결과:
    data/fig_pattern_실습실_co2.png 등 그래프 4장
    data/day_summary.csv  (실습실 하루마다 한 줄)
"""

# 수정 기록
# - 2026-10-22 처음 작성 (패턴 그래프, 반응 시간, 일정과 안 맞는 날)
# - 2026-10-22 공휴일에 2026-05-01, 2026-07-17 추가 (지원 확인)
# - 2026-10-22 과정 사이 휴강 2026-09-23~30을 쉬는 날로, 45~50명 시기 끝을 09-22로 (지원 확인)
# - 2026-10-22 그래프만 채운 값 포함으로 바꿈 (회의실 지그재그 해결). 표와 반응 시간은 진짜 값만 그대로

import matplotlib

matplotlib.use("Agg")  # 창을 띄우지 않고 파일로만 저장
import matplotlib.pyplot as plt
import pandas as pd

from split import read_grid

plt.rcParams["font.family"] = "AppleGothic"  # Mac 기본 한글 글꼴
plt.rcParams["axes.unicode_minus"] = False

# 평일 공휴일(대체공휴일 포함). 주말과 겹치는 공휴일은 어차피 쉬는 날이라 뺐다.
# 2026-05-01(노동절), 2026-07-17(제헌절)은 수업을 쉬었다(지원 확인).
# 쉬는 날에도 수강생이 자율로 들어올 수 있어서, "쉬는 날인데 오름"은 고장이 아니라 자율 학습일 수 있다
HOLIDAYS = {
    "2025-10-03", "2025-10-06", "2025-10-07", "2025-10-08", "2025-10-09", "2025-12-25",
    "2026-01-01", "2026-02-16", "2026-02-17", "2026-02-18", "2026-03-02", "2026-05-05",
    "2026-05-01", "2026-05-25", "2026-06-03", "2026-07-17", "2026-08-17", "2026-09-24", "2026-09-25", "2026-10-05",
    "2026-10-09",
}
# 과정 사이 휴강(지원 확인): 45~50명 기수 종료 2026-09-22, 17명 기수 시작 2026-10-01
HOLIDAYS |= {f"2026-09-{d}" for d in range(23, 31)}

# 실습실 사용 인원 시기(지원 확인). 이전 기수 → 45~50명 경계는 대략 2025-12말(정확한 날 모름), 45~50명 종료 2026-09-22, 17명 시작 2026-10-01
PERIODS = [
    ("이전 기수 (~2025-12)", "2025-09-03", "2026-01-01"),
    ("45~50명 (2026-01~09-22)", "2026-01-01", "2026-09-23"),
    ("약 17명 (2026-10~)", "2026-10-01", "2026-12-31"),
]

# 임시 기준. 결과를 보고 바꿀 수 있다
RISE_PPM = 50        # 아침 기준값보다 이만큼 오르면 "오르기 시작"
CLASS_MIN_RANGE = 100  # 수업일인데 하루 변화 폭이 이보다 작으면 "안 오름"
REST_MAX_RANGE = 200   # 쉬는 날인데 하루 변화 폭이 이보다 크면 "오름"
MIN_REAL_RATIO = 0.8   # 08~18시 칸 중 진짜 측정값이 이 비율보다 적으면 판단하지 않음


def add_day_info(g):
    g = g.copy()
    g["date"] = g["bin"].dt.strftime("%Y-%m-%d")
    g["minute"] = g["bin"].dt.hour * 60 + g["bin"].dt.minute
    weekday = g["bin"].dt.dayofweek < 5
    g["class_day"] = weekday & ~g["date"].isin(HOLIDAYS)
    g["period"] = ""
    for name, start, stop in PERIODS:
        g.loc[(g["date"] >= start) & (g["date"] < stop), "period"] = name
    return g


def plot_pattern(g, loc, m, unit):
    # 그래프는 15분까지 채운 값도 쓴다. 회의실은 10분마다 보내서 진짜 값만 쓰면
    # 5분 칸마다 평균에 들어가는 날이 달라져 지그재그가 생긴다 (2026-10-22 확인)
    d = g[(g["location"] == loc) & g[m].notna()]
    fig, ax = plt.subplots(figsize=(10, 4.5))
    for name, _, _ in PERIODS:
        part = d[d["class_day"] & (d["period"] == name)]
        if part.empty:
            continue
        curve = part.groupby("minute")[m].mean()
        ax.plot(curve.index / 60, curve.values, label="수업일 · " + name)
    rest = d[~d["class_day"]].groupby("minute")[m].mean()
    ax.plot(rest.index / 60, rest.values, color="gray", linestyle="--", label="쉬는 날 (전체)")
    if loc == "실습실":
        for h in [9, 11.5, 13, 18]:
            ax.axvline(h, color="lightgray", linewidth=1)
    ax.set_xticks(range(0, 25, 3))
    ax.set_xlabel("시각")
    ax.set_ylabel(unit)
    ax.set_title(f"{loc} {m} 시간대별 평균 (15분까지 채운 값 포함)")
    ax.legend(fontsize=8)
    fig.tight_layout()
    path = f"data/fig_pattern_{loc}_{m}.png"
    fig.savefig(path, dpi=120)
    plt.close(fig)
    return path


def first_time(series, condition):
    hit = series[condition]
    return hit.index[0] if len(hit) else None


def hhmm(minute):
    return "" if minute is None or pd.isna(minute) else f"{int(minute) // 60:02d}:{int(minute) % 60:02d}"


def day_summary(g):
    d = g[(g["location"] == "실습실") & g["real_co2"]]
    rows = []
    for date, day in d.groupby("date"):
        s = day.set_index("minute")["co2"]
        work = s[(s.index >= 8 * 60) & (s.index < 18 * 60)]
        row = {
            "date": date,
            "weekday": "월화수목금토일"[day["bin"].iloc[0].dayofweek],
            "class_day": bool(day["class_day"].iloc[0]),
            "period": day["period"].iloc[0],
            "real_ratio_08_18": round(len(work) / 120, 2),
        }
        if row["real_ratio_08_18"] >= MIN_REAL_RATIO:
            base = s[(s.index >= 8 * 60) & (s.index < 9 * 60)].median()
            rise = first_time(work, work >= base + RISE_PPM)
            morning = s[(s.index >= 9 * 60) & (s.index < 11 * 60 + 30)]
            lunch = s[(s.index >= 11 * 60 + 30) & (s.index < 13 * 60 + 30)]
            row.update({
                "base_08_09": round(base, 1),
                "rise_at": hhmm(rise),
                "rise_vs_0900_min": None if rise is None else rise - 9 * 60,
                "morning_peak_at": hhmm(morning.idxmax()) if len(morning) else "",
                "lunch_low_at": hhmm(lunch.idxmin()) if len(lunch) else "",
                "range_08_18": round(work.max() - work.min(), 1),
            })
        rows.append(row)
    out = pd.DataFrame(rows)
    out["mismatch"] = ""
    judged = out["real_ratio_08_18"] >= MIN_REAL_RATIO
    out.loc[judged & out["class_day"] & (out["range_08_18"] < CLASS_MIN_RANGE), "mismatch"] = "수업일인데 안 오름"
    out.loc[judged & ~out["class_day"] & (out["range_08_18"] > REST_MAX_RANGE), "mismatch"] = "쉬는 날인데 오름"
    out.loc[~judged, "mismatch"] = "데이터 부족"
    return out


def main():
    g = add_day_info(read_grid())

    print("== 그래프 ==")
    for loc in ["실습실", "회의실"]:
        print(plot_pattern(g, loc, "co2", "CO₂ (ppm)"))
        print(plot_pattern(g, loc, "temperature", "온도 (℃)"))

    print("\n== 실습실 CO₂ 수업일 시간별 평균 (시기별) ==")
    d = g[(g["location"] == "실습실") & g["real_co2"] & g["class_day"]].copy()
    d["hour"] = d["bin"].dt.hour
    table = d.pivot_table(index="hour", columns="period", values="co2", aggfunc="mean").round(0)
    table = table[[name for name, _, _ in PERIODS if name in table.columns]]
    print(table.to_string())

    days = day_summary(g)
    days.to_csv("data/day_summary.csv", index=False)

    ok = days[days["class_day"] & (days["mismatch"] == "")]
    print("\n== 실습실 수업일 반응 (일정과 맞는 날만) ==")
    print("시기별 'CO₂가 오르기 시작한 시각 - 09:00' (분, 음수면 9시 전에 오름)")
    print(ok.groupby("period")["rise_vs_0900_min"].describe()[["count", "25%", "50%", "75%"]].to_string())
    print("\n오전 최고 시각과 점심 최저 시각 (가장 흔한 값)")
    print(ok.groupby("period")[["morning_peak_at", "lunch_low_at"]].agg(lambda x: x.mode().iloc[0] if len(x.mode()) else "").to_string())

    print("\n== 일정과 안 맞는 날 ==")
    print(days["mismatch"].replace("", "맞음").value_counts().to_string())
    cols = ["date", "weekday", "period", "real_ratio_08_18", "base_08_09", "range_08_18", "mismatch"]
    odd = days[days["mismatch"].isin(["수업일인데 안 오름", "쉬는 날인데 오름"])]
    print(odd[cols].to_string(index=False))
    print("\n저장: data/day_summary.csv")


if __name__ == "__main__":
    main()
