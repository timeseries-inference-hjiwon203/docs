"""5분 칸 표 → 모델 입력. 학습(train.py)·채점(evaluate.py)이 같은 코드를 쓰고, 과제 8 서비스도 그대로 쓴다.

칸마다 만드는 숫자 (plan.md '입력과 출력'):
  과거 칸  센서 3개(정규화) + 채움 표시 3개 + 시간 4개 + 공간 1개 + 일정 4개(use_schedule일 때)
  미래 칸  시간 4개 + 일정 4개(use_schedule일 때). 앞으로 60분 동안 미리 알 수 있는 것만
정답: 12칸(5~60분 뒤) × (CO₂, 온도)
  target="delta"     (미래 값 - 지금 값) / 학습 기간 60분 변화량의 표준편차   ← 기본. 0을 내면 '현재값 유지'와 같다
  target="absolute"  (미래 값 - 평균) / 값의 표준편차
변화량을 '값의 표준편차'(온도 3.7℃)로 나누면 온도 60분 변화(보통 0.2℃)가 0.05쯤으로 작아져, CO₂(86ppm/444 = 0.19)에
비해 오차 함수에서 거의 무시된다. 그래서 변화량은 '변화량의 표준편차'로 나눠 두 항목이 비슷한 크기가 되게 한다.

두 공간의 칸을 한 줄로 이어 붙여(실습실 다음 회의실) 행렬 하나로 만들고, 기준 시각을 그 행 번호로 다룬다.
창이 두 공간의 경계를 넘지 않게 공간마다 시작·끝 행 번호를 기억한다.
5분 칸 표는 공간마다 빈 칸 없이 이어진 시각이라(resample.py) 행 번호 차이 1 = 5분이다.

정규화 값은 학습 기간 값(norm_stats.json)으로만 만든다(SC-003). 공간을 한 모델로 학습하므로
두 공간의 평균·표준편차를 건수로 가중해 합친 값 하나를 쓴다. 처음 보는 공간 시험(E6)에서는
학습에 쓰는 공간의 값만 합친다(norm_locations).
"""

# 수정 기록
# - 2026-10-25 처음 작성 (입력 행렬, 학습 기준 시각 고르기, 묶음 만들기, 예측값을 원래 단위로)
# - 2026-10-25 변화량 정답을 '60분 변화량의 표준편차'로 나누도록 바꿈. 값의 표준편차로 나누면 온도 변화가 CO₂보다 훨씬 작은 숫자가 되어
#              오차 함수에서 거의 무시됐다(E1에서 온도 60분 오차가 현재값 유지보다 나빠짐)
# - 2026-10-25 season 선택 추가: 과거 칸에 '1년 중 며칠째' sin·cos (냉난방 계절을 모델이 알게, 온도용 시험)
# - 2026-10-25 location_input 선택 추가: False면 is_lab 칸을 뺀다 (E6. 한 공간으로만 학습하면 is_lab이 늘 같아, 다른 공간의 값은 처음 보는 값이 되므로)

import json

import numpy as np
import pandas as pd

from schedule import SCHEDULE_COLUMNS, schedule_columns
from split import SPLITS, read_grid

LOCATIONS = ["실습실", "회의실"]
SENSORS = ["co2", "temperature", "humidity"]
TARGETS = ["co2", "temperature"]
HORIZON = 12                     # 60분 = 5분 칸 12개
TIME_COLUMNS = ["tod_sin", "tod_cos", "dow_sin", "dow_cos"]


def pooled_stats(stats, locations):
    """공간별 평균·표준편차를 건수로 가중해 합친다. {항목: (평균, 표준편차)}"""
    out = {}
    for m in SENSORS:
        n = np.array([stats[loc][m]["n"] for loc in locations], dtype=float)
        mean = np.array([stats[loc][m]["mean"] for loc in locations])
        std = np.array([stats[loc][m]["std"] for loc in locations])
        mu = (n * mean).sum() / n.sum()
        var = (n * (std ** 2 + mean ** 2)).sum() / n.sum() - mu ** 2
        out[m] = (float(mu), float(np.sqrt(var)))
    return out


def time_columns(times):
    """하루 안 시각과 요일을 시계 바늘처럼 sin·cos 두 숫자로. 23시와 0시, 일요일과 월요일이 가깝다."""
    minutes = times.dt.hour * 60 + times.dt.minute
    day = 2 * np.pi * minutes / (24 * 60)
    week = 2 * np.pi * (times.dt.dayofweek * 24 * 60 + minutes) / (7 * 24 * 60)
    return pd.DataFrame({"tod_sin": np.sin(day), "tod_cos": np.cos(day),
                         "dow_sin": np.sin(week), "dow_cos": np.cos(week)})


class Data:
    """두 공간의 5분 칸 표를 모델 입력 행렬로 바꿔 들고 있는다."""

    def __init__(self, history_bins, use_schedule=True, target="delta",
                 grid_path="data/grid_5min.csv.gz", stats_path="data/norm_stats.json",
                 norm_locations=LOCATIONS, season=False, location_input=True):
        assert target in ("delta", "absolute")
        self.history_bins, self.use_schedule, self.target = history_bins, use_schedule, target
        self.season = season
        self.location_input = location_input
        with open(stats_path) as f:
            self.norm = pooled_stats(json.load(f), norm_locations)

        grid = read_grid(grid_path)
        past, future, raw, real, starts, ends, rows = [], [], [], [], [], [], []
        n = 0
        for loc in LOCATIONS:
            g = grid[grid["location"] == loc].sort_values("bin").reset_index(drop=True)
            gap = g["bin"].diff().dropna()
            assert (gap == pd.Timedelta("5min")).all(), f"{loc}: 5분 칸이 이어져 있지 않다"
            p, fu = self._columns(g, loc)
            past.append(p)
            future.append(fu)
            raw.append(g[SENSORS].to_numpy(dtype=float))
            real.append(np.stack([g["real_" + m].to_numpy(dtype=bool) for m in SENSORS], axis=1))
            rows.append(pd.Series(np.arange(n, n + len(g)), index=g["bin"]))
            starts.append(n)
            n += len(g)
            ends.append(n)

        self.past = np.concatenate(past).astype(np.float32)        # [행, 과거 칸 숫자]
        self.future = np.concatenate(future).astype(np.float32)    # [행, 미래 칸 숫자]
        self.raw = np.concatenate(raw)                              # [행, 3] 15분까지 채운 원래 단위 값(긴 결측은 NaN)
        self.real = np.concatenate(real)                            # [행, 3] 진짜 측정값이 있는 칸
        self.times = pd.concat([r.index.to_series() for r in rows]).reset_index(drop=True)
        self.loc_id = np.concatenate([np.full(e - s, i) for i, (s, e) in enumerate(zip(starts, ends))])
        self.loc_start, self.loc_end = np.array(starts)[self.loc_id], np.array(ends)[self.loc_id]
        self.row_of = {loc: r for loc, r in zip(LOCATIONS, rows)}  # 공간 → (칸 시각 → 행 번호)

        self.target_idx = [SENSORS.index(m) for m in TARGETS]
        self.mean = np.array([self.norm[m][0] for m in TARGETS])
        self.std = np.array([self.norm[m][1] for m in TARGETS])

        # 학습 기간 60분 변화량의 표준편차 (정규화에 쓰는 공간만)
        t = np.arange(len(self.raw) - HORIZON)
        same = self.loc_id[t] == self.loc_id[t + HORIZON]
        in_train = self.times.values[t + HORIZON] < SPLITS["train"][1].to_datetime64()
        in_norm = np.isin(self.loc_id[t], [LOCATIONS.index(x) for x in norm_locations])
        d = self.raw[t + HORIZON][:, self.target_idx] - self.raw[t][:, self.target_idx]
        ok = same & in_train & in_norm
        self.delta_std = np.array([np.nanstd(d[ok, i]) for i in range(len(TARGETS))])
        self.scale = self.delta_std if target == "delta" else self.std

    @property
    def n_past(self):
        return self.past.shape[1]

    @property
    def n_future(self):
        return self.future.shape[1]

    def _columns(self, g, loc):
        """한 공간의 과거 칸 숫자, 미래 칸 숫자."""
        cols = {}
        for m in SENSORS:
            mu, sd = self.norm[m]
            # 15분 넘는 빈 칸은 앞 값으로 더 채우고(그래도 없으면 평균 = 0) 채움 표시를 1로 둔다.
            # 학습 기준 시각에서는 이런 칸이 창에 없도록 따로 거른다(train_origins)
            cols[m] = ((g[m].ffill() - mu) / sd).fillna(0.0).to_numpy()
        for m in SENSORS:
            cols["filled_" + m] = (~g["real_" + m].astype(bool)).astype(float).to_numpy()
        tc = time_columns(g["bin"])
        for c in TIME_COLUMNS:
            cols[c] = tc[c].to_numpy()
        if self.location_input:
            cols["is_lab"] = np.full(len(g), 1.0 if loc == "실습실" else 0.0)
        if self.season:
            # 1년 중 며칠째를 시계 바늘처럼. 12월 31일과 1월 1일이 가깝다. 학습 기간이 1년뿐이라 '날짜 외우기'가 될 수도 있어 시험용 선택으로 둔다
            year = 2 * np.pi * (g["bin"].dt.dayofyear - 1) / 365.25
            cols["doy_sin"], cols["doy_cos"] = np.sin(year).to_numpy(), np.cos(year).to_numpy()
        future = {c: tc[c].to_numpy() for c in TIME_COLUMNS}
        if self.use_schedule:
            sc = schedule_columns(g["bin"])
            for c in SCHEDULE_COLUMNS:
                cols[c] = sc[c].to_numpy()
                future[c] = sc[c].to_numpy()
        self.past_columns, self.future_columns = list(cols), list(future)
        return np.stack(list(cols.values()), axis=1), np.stack(list(future.values()), axis=1)

    def rows(self, location, times):
        """공간과 칸 시각 목록 → 행 번호. 표에 없는 시각이면 오류."""
        return self.row_of[location].loc[pd.DatetimeIndex(times)].to_numpy()

    def train_origins(self, split="train", locations=LOCATIONS):
        """학습에 쓸 기준 시각(행 번호).

        - 과거 창 전체에 15분 넘는 빈 칸이 없다 (센서 3개 모두)
        - 지금 값(CO₂·온도)이 있다
        - 정답 12칸 중 진짜 측정값이 하나라도 있다
        - 창과 정답 칸이 모두 같은 공간, 정답 마지막 칸까지 그 기간 안 (학습 정답이 9월로 넘어가지 않게)
        """
        start, stop = SPLITS[split]
        t = np.arange(len(self.raw))
        ok_cell = ~np.isnan(self.raw).any(axis=1)
        bad = np.concatenate([[0], np.cumsum(~ok_cell)])
        L = self.history_bins
        lo = np.clip(t - L + 1, 0, None)
        window_ok = (bad[t + 1] - bad[lo]) == 0
        inside = (t - L + 1 >= self.loc_start) & (t + HORIZON < self.loc_end)
        last = np.clip(t + HORIZON, None, len(t) - 1)
        in_split = (self.times.values >= start.to_datetime64()) & (self.times[last].values < stop.to_datetime64())
        # 정답 칸에 진짜 값이 하나라도
        real_t = self.real[:, self.target_idx].any(axis=1)
        has_answer = np.zeros(len(t), dtype=bool)
        for k in range(1, HORIZON + 1):
            has_answer[: len(t) - k] |= real_t[k:]
        base_ok = ~np.isnan(self.raw[:, self.target_idx]).any(axis=1)
        loc_ok = np.isin(self.loc_id, [LOCATIONS.index(x) for x in locations])
        return t[window_ok & inside & in_split & has_answer & base_ok & loc_ok]

    def batch(self, origins):
        """기준 시각 행 번호들 → (과거 칸, 미래 칸, 정답, 정답 표시, 지금 값).

        과거 칸 [B, L, n_past], 미래 칸 [B, 12, n_future], 정답 [B, 12, 2](정규화), 정답 표시 [B, 12, 2](진짜 값만 True),
        지금 값 [B, 2](원래 단위). 창이 공간 시작 전으로 나가면 공간 첫 칸으로 붙인다(채점 때만 생길 수 있음).
        """
        o = np.asarray(origins)
        lo, hi = self.loc_start[o][:, None], self.loc_end[o][:, None] - 1
        past_idx = np.clip(o[:, None] + np.arange(-self.history_bins + 1, 1), lo, hi)
        fut_idx = np.clip(o[:, None] + np.arange(1, HORIZON + 1), lo, hi)
        base = self.raw[o][:, self.target_idx]
        y = self.raw[fut_idx][:, :, self.target_idx]
        mask = self.real[fut_idx][:, :, self.target_idx] & ~np.isnan(y) & ~np.isnan(base)[:, None, :]
        if self.target == "delta":
            yn = (y - base[:, None, :]) / self.scale
        else:
            yn = (y - self.mean) / self.scale
        yn = np.where(mask, yn, 0.0).astype(np.float32)
        return self.past[past_idx], self.future[fut_idx], yn, mask, base

    def to_original(self, out, base):
        """모델 출력 [B, 12, 2] → 원래 단위(ppm, ℃) 예측값."""
        if self.target == "delta":
            return base[:, None, :] + out * self.scale
        return self.mean + out * self.scale
