"""Displacement — DEF-DISP-01.

A single candle, or a run of <= 3 consecutive same-direction candles, ending at
bar ``i``, whose summed body ``sum(|close-open|) >= disp_mult x ATR``. The
"leaves at least one FVG" clause of DEF-DISP-01 is enforced by the caller
(``mss``), which also selects that FVG.

Upper bound (spec A5 #3 / DEF-DISP-01): a single candle whose body exceeds
``disp_max x ATR`` is news-print behaviour with untradeable retracements -> reject.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

BULL, BEAR = "bull", "bear"


def is_displacement(
    df: pd.DataFrame,
    i: int,
    atr_value: float,
    direction: str,
    disp_mult: float,
    disp_max: float = 4.0,
    max_run: int = 3,
) -> bool:
    """True if a valid displacement in ``direction`` ends at bar ``i``."""
    if i < 0 or not np.isfinite(atr_value) or atr_value <= 0:
        return False
    opens = df["open"].to_numpy(dtype=float)
    closes = df["close"].to_numpy(dtype=float)

    lo_thresh = disp_mult * atr_value
    hi_thresh = disp_max * atr_value
    bull = direction == BULL

    summed = 0.0
    for run in range(1, max_run + 1):
        j = i - run + 1
        if j < 0:
            break
        body = closes[j] - opens[j]
        same_dir = body > 0 if bull else body < 0
        if not same_dir:
            break
        mag = abs(body)
        if mag > hi_thresh:          # single news-print candle -> reject outright
            return False
        summed += mag
        if summed >= lo_thresh:
            return True
    return False
