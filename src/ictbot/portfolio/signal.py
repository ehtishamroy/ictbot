"""DEF-TSMOM-01 — absolute (time-series) momentum signal."""
from __future__ import annotations

import numpy as np


def tsmom_signs(price_arr: np.ndarray, d: int, lookback_months: int,
                skip_recent_month: int, month_days: int) -> np.ndarray:
    """Sign of trailing momentum per instrument at price-row ``d``.

    mom = P[d - skip] / P[d - skip - lookback] - 1, computed per column;
    +1/-1/0 (0 when flat or history insufficient / price missing).
    """
    m = price_arr.shape[1]
    skip = skip_recent_month * month_days
    lb = lookback_months * month_days
    i_recent = d - skip
    i_old = d - skip - lb
    if i_old < 0:
        return np.zeros(m)
    p_recent = price_arr[i_recent]
    p_old = price_arr[i_old]
    signs = np.zeros(m)
    with np.errstate(invalid="ignore", divide="ignore"):
        mom = p_recent / p_old - 1.0
    ok = np.isfinite(mom)
    signs[ok] = np.sign(mom[ok])
    return signs
