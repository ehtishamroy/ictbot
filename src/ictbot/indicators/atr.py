"""ATR(14) — Average True Range.

Uses Wilder's RMA smoothing (recursive: ``y[i] = (1-1/n)*y[i-1] + (1/n)*TR[i]``),
which is what MT5's ``iATR`` and Pine's ``ta.atr`` compute — so the Python
research numbers and the MQL5/Pine ports stay comparable (spec D2/D4). ATR at bar
*i* uses only bars up to and including *i*; the first ``period-1`` values are NaN.
"""
from __future__ import annotations

import pandas as pd


def true_range(df: pd.DataFrame) -> pd.Series:
    """True Range = max(H-L, |H-prevC|, |L-prevC|). First bar = H-L."""
    prev_close = df["close"].shift(1)
    tr = pd.concat(
        [
            df["high"] - df["low"],
            (df["high"] - prev_close).abs(),
            (df["low"] - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Wilder ATR over ``period`` bars (NaN until ``period`` bars exist)."""
    tr = true_range(df)
    return tr.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()
