"""수업 일정과 인원. 미리 알 수 있는 운영 정보만 담는다.

과제 3 입력(features.py)과 과제 8 서비스가 같은 값을 쓴다.
공휴일·휴강 목록은 과제 2 patterns.py의 HOLIDAYS를 그대로 옮겼다(patterns.py는 그래프 도구까지 불러와서 여기서 따로 둠).

수업 일정(지원 확인): 공휴일을 뺀 평일 09:00~18:00, 점심 11:30~13:00.
인원(지원 확인, 이전 기수는 모름 → 40명 추정):
  2025-09-03 ~ 2025-12-31  40명 (이전 기수, 추정. 기수 경계 2025-12말의 정확한 날을 몰라 1월 1일로 둠)
  2026-01-01 ~ 2026-08-31  48명 (45~50명의 가운데)
  2026-09-01 ~ 2026-09-22  45명 (9월은 45명 내외)
  2026-09-23 ~ 2026-09-30   0명 (과정 사이 휴강)
  2026-10-01 ~             17명
"""

# 수정 기록
# - 2026-10-25 처음 작성 (patterns.py의 HOLIDAYS 옮김, 기수별 인원, 칸마다 일정 숫자 만들기)

import numpy as np
import pandas as pd

TZ = "Asia/Seoul"

# 평일 공휴일(대체공휴일 포함) + 과정 사이 휴강. patterns.py와 같다
HOLIDAYS = {
    "2025-10-03", "2025-10-06", "2025-10-07", "2025-10-08", "2025-10-09", "2025-12-25",
    "2026-01-01", "2026-02-16", "2026-02-17", "2026-02-18", "2026-03-02", "2026-05-05",
    "2026-05-01", "2026-05-25", "2026-06-03", "2026-07-17", "2026-08-17", "2026-09-24", "2026-09-25", "2026-10-05",
    "2026-10-09",
}
HOLIDAYS |= {f"2026-09-{d}" for d in range(23, 31)}

HEADCOUNT = [            # (시작일, 인원): 시작일부터 다음 줄 시작일 전까지
    ("2025-09-03", 40),
    ("2026-01-01", 48),
    ("2026-09-01", 45),
    ("2026-09-23", 0),
    ("2026-10-01", 17),
]
HEADCOUNT_SCALE = 50     # 인원을 50으로 나눠 0~1 근처 숫자로 넣는다

CLASS_START, CLASS_END = 9 * 60, 18 * 60          # 분 단위 (09:00, 18:00)
LUNCH_START, LUNCH_END = 11 * 60 + 30, 13 * 60    # 11:30, 13:00

SCHEDULE_COLUMNS = ["class_day", "in_class", "lunch", "headcount"]


def headcount(times):
    """시각마다 그 시기 기수 인원(명)."""
    starts = pd.to_datetime([d for d, _ in HEADCOUNT]).tz_localize(TZ)
    counts = np.array([n for _, n in HEADCOUNT], dtype=float)
    pos = np.searchsorted(starts.values, times.dt.tz_convert(TZ).values, side="right") - 1
    return pd.Series(counts[np.clip(pos, 0, None)], index=times.index)


def schedule_columns(times):
    """5분 칸 시작 시각(times, 한국 시각)마다 일정 숫자 4개. 모두 0~1.

    class_day  수업일(공휴일·휴강이 아닌 평일)이면 1
    in_class   수업일 09:00~18:00이면서 점심이 아니면 1
    lunch      수업일 점심 11:30~13:00이면 1
    headcount  그 시기 인원 / 50
    """
    t = times.dt.tz_convert(TZ)
    minutes = t.dt.hour * 60 + t.dt.minute
    class_day = (t.dt.dayofweek < 5) & ~t.dt.strftime("%Y-%m-%d").isin(HOLIDAYS)
    lunch = class_day & (minutes >= LUNCH_START) & (minutes < LUNCH_END)
    in_class = class_day & (minutes >= CLASS_START) & (minutes < CLASS_END) & ~lunch
    return pd.DataFrame({
        "class_day": class_day.astype(float),
        "in_class": in_class.astype(float),
        "lunch": lunch.astype(float),
        "headcount": headcount(times) / HEADCOUNT_SCALE,
    })
