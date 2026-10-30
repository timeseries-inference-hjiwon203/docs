"""60분 예측 모델 3종 (GRU, LSTM, TCN). 세 모델 모두 같은 틀이다.

    과거 칸 [B, L, n_past] ──몸통──▶ 요약 숫자 64개 ─┐
    앞으로 60분 칸 [B, 12, n_future] ── 펼침 ────────┴─▶ 출력층 ─▶ [B, 12, 2] (12칸 × CO₂·온도)

몸통만 다르다.
  GRU, LSTM  한 칸씩 읽으며 메모를 고친다(순환 신경망). 마지막 칸을 읽은 뒤의 메모가 요약
  TCN        3칸 창을 칸 건너뛰기(1·2·4·8…칸 간격)로 쌓아 과거 전체를 본다(합성곱). 마지막 칸 위치의 값이 요약
"""

# 수정 기록
# - 2026-10-25 처음 작성 (GRU, LSTM, TCN 몸통 + 같은 출력층)
# - 2026-10-25 dropout 선택 추가 (E1이 2에폭 만에 외우기 시작해서)

import torch
from torch import nn

from features import HORIZON, TARGETS


class TCNBody(nn.Module):
    """과거만 보는 3칸 창을 칸 건너뛰기로 쌓는다. 층마다 앞 결과를 더해(잔차 연결) 깊어져도 학습이 잘 된다."""

    def __init__(self, n_in, hidden, history_bins, kernel=3, dropout=0.0):
        super().__init__()
        self.drop = nn.Dropout(dropout)
        self.inp = nn.Conv1d(n_in, hidden, 1)
        dilations, reach = [], 1
        while reach < history_bins:          # 창이 과거 전체(history_bins칸)를 덮을 때까지 층을 쌓는다
            d = 2 ** len(dilations)
            dilations.append(d)
            reach += (kernel - 1) * d
        self.dilations = dilations
        self.convs = nn.ModuleList(nn.Conv1d(hidden, hidden, kernel, dilation=d) for d in dilations)
        self.kernel = kernel

    def forward(self, x):                    # x [B, L, n_in]
        h = self.inp(x.transpose(1, 2))      # [B, hidden, L]
        for d, conv in zip(self.dilations, self.convs):
            pad = (self.kernel - 1) * d      # 왼쪽(과거)에만 채워서 미래 칸을 보지 않는다
            h = h + self.drop(torch.relu(conv(nn.functional.pad(h, (pad, 0)))))
        return h[:, :, -1]                   # 마지막 칸(지금) 위치


class RNNBody(nn.Module):
    def __init__(self, kind, n_in, hidden, layers=2, dropout=0.0):
        super().__init__()
        cls = {"gru": nn.GRU, "lstm": nn.LSTM}[kind]
        self.rnn = cls(n_in, hidden, num_layers=layers, batch_first=True, dropout=dropout)  # 층 사이에 dropout

    def forward(self, x):
        out, _ = self.rnn(x)
        return out[:, -1]                    # 마지막 칸을 읽은 뒤의 메모


class Forecaster(nn.Module):
    def __init__(self, kind, n_past, n_future, history_bins, hidden=64, dropout=0.0):
        """dropout: 학습 때 숫자 일부를 무작위로 0으로 만들어, 특정 숫자 몇 개에 기대 외우는 것을 막는다(채점 때는 꺼짐)."""
        super().__init__()
        if kind == "tcn":
            self.body = TCNBody(n_past, hidden, history_bins, dropout=dropout)
        else:
            self.body = RNNBody(kind, n_past, hidden, dropout=dropout)
        self.head = nn.Sequential(
            nn.Linear(hidden + HORIZON * n_future, 128), nn.ReLU(), nn.Dropout(dropout),
            nn.Linear(128, HORIZON * len(TARGETS)),
        )
        # 출력층 마지막 가중치를 0으로 시작: 처음에는 모든 출력이 0이라 변화량 방식이면 '현재값 유지'에서 출발한다
        nn.init.zeros_(self.head[-1].weight)
        nn.init.zeros_(self.head[-1].bias)

    def forward(self, past, future):
        z = torch.cat([self.body(past), future.flatten(1)], dim=1)
        return self.head(z).view(-1, HORIZON, len(TARGETS))


def count_params(model):
    return sum(p.numel() for p in model.parameters())
