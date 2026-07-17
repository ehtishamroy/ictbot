"""Swings — DEF-SWING-01 (fractal pivots, confirmed k bars late, never repaint).

A **swing high** at bar *i* is a high strictly greater than the highs of the
``k`` bars on each side; a **swing low** is the mirror. The crucial rule: a pivot
is only CONFIRMED ``k`` bars after it forms, and code must never act on an
unconfirmed pivot (spec DEF-SWING-01 / D6 bug #1 "repainting swings").

``compute_swings`` returns, per bar:
  * ``is_swing_high`` / ``is_swing_low`` — marks the pivot bar itself (for plots);
  * ``conf_sh`` / ``conf_sl`` — the price of the most recent swing high/low that
    is *confirmed as of this bar*, plus its bar position ``conf_sh_idx`` /
    ``conf_sl_idx``. These are the look-ahead-safe values the strategy logic uses.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def _pivot_mask(values: np.ndarray, k: int, high: bool) -> np.ndarray:
    n = len(values)
    mask = np.zeros(n, dtype=bool)
    for i in range(k, n - k):
        left = values[i - k:i]
        right = values[i + 1:i + k + 1]
        if high:
            if values[i] > left.max() and values[i] > right.max():
                mask[i] = True
        else:
            if values[i] < left.min() and values[i] < right.min():
                mask[i] = True
    return mask


def _confirmed_series(pivot_mask: np.ndarray, prices: np.ndarray, k: int):
    """For each bar t, the (price, idx) of the latest pivot confirmed by t.

    A pivot at position p is confirmed at position p+k (available from t=p+k on).
    """
    n = len(prices)
    conf_val = np.full(n, np.nan)
    conf_idx = np.full(n, -1, dtype=int)
    pivots = np.flatnonzero(pivot_mask)  # increasing positions
    ptr = 0
    last_val, last_idx = np.nan, -1
    for t in range(n):
        while ptr < len(pivots) and pivots[ptr] + k <= t:
            last_idx = int(pivots[ptr])
            last_val = float(prices[last_idx])
            ptr += 1
        conf_val[t] = last_val
        conf_idx[t] = last_idx
    return conf_val, conf_idx


def compute_swings(df: pd.DataFrame, k: int) -> pd.DataFrame:
    """Return per-bar swing markers and non-repainting confirmed-swing levels."""
    highs = df["high"].to_numpy(dtype=float)
    lows = df["low"].to_numpy(dtype=float)

    is_sh = _pivot_mask(highs, k, high=True)
    is_sl = _pivot_mask(lows, k, high=False)

    conf_sh, conf_sh_idx = _confirmed_series(is_sh, highs, k)
    conf_sl, conf_sl_idx = _confirmed_series(is_sl, lows, k)

    return pd.DataFrame(
        {
            "is_swing_high": is_sh,
            "is_swing_low": is_sl,
            "conf_sh": conf_sh,
            "conf_sh_idx": conf_sh_idx,
            "conf_sl": conf_sl,
            "conf_sl_idx": conf_sl_idx,
        },
        index=df.index,
    )
