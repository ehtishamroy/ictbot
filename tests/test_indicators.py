"""Phase 2 — ATR, non-repainting swings, and BOS/CHoCH structure.

Fixtures are hand-built so the expected pivots/events are computed by hand, not
by the code under test.
"""
import numpy as np
import pandas as pd

from ictbot.indicators.atr import atr, true_range
from ictbot.indicators.structure import (
    BOS_BULL,
    CHOCH_BEAR,
    DOWN,
    NEUTRAL,
    UP,
    compute_structure,
)
from ictbot.indicators.swings import compute_swings


def _df(rows):
    n = len(next(iter(rows.values())))
    idx = pd.date_range("2024-01-15 13:30", periods=n, freq="5min", tz="UTC")
    return pd.DataFrame(rows, index=idx)


# --- ATR --------------------------------------------------------------------
def test_true_range_and_atr():
    df = _df({
        "high": [10.0, 11.0, 9.0],
        "low": [8.0, 9.0, 7.0],
        "close": [9.0, 10.0, 8.0],
    })
    tr = true_range(df)
    assert list(tr) == [2.0, 2.0, 3.0]  # first bar = H-L; then TR incl. prev close
    a = atr(df, period=2)               # RMA alpha=0.5: NaN, 2.0, 2.5
    assert np.isnan(a.iloc[0])
    assert a.iloc[1] == 2.0
    assert a.iloc[2] == 2.5


# --- Swings: correct pivots AND confirmation delay (no repaint) -------------
def test_swings_and_confirmation_delay():
    df = _df({
        "high": [10.0, 12.0, 8.0, 9.0, 7.0],
        "low": [5.0, 6.0, 3.0, 4.0, 2.0],
        "close": [10.0, 12.0, 8.0, 9.0, 7.0],
    })
    s = compute_swings(df, k=1)
    # swing highs at bars 1 and 3; swing low at bar 2
    assert list(np.flatnonzero(s["is_swing_high"].to_numpy())) == [1, 3]
    assert list(np.flatnonzero(s["is_swing_low"].to_numpy())) == [2]
    # non-repaint: bar 1's swing high is NaN until it confirms one bar later (bar 2)
    assert np.isnan(s["conf_sh"].iloc[1])
    assert s["conf_sh"].iloc[2] == 12.0
    assert s["conf_sh"].iloc[3] == 12.0   # bar-3 pivot not yet confirmed here
    assert s["conf_sh"].iloc[4] == 9.0
    # swing low confirms one bar late too
    assert np.isnan(s["conf_sl"].iloc[2])
    assert s["conf_sl"].iloc[3] == 3.0


# --- Structure: NEUTRAL -> BOS (bull) -> CHoCH (bear) ------------------------
def test_bos_then_choch():
    df = _df({
        "high": [10.0, 11.0, 9.0, 13.0, 14.0, 13.0, 12.0, 11.0],
        "low": [8.0, 9.0, 7.0, 8.0, 12.0, 10.0, 11.0, 8.0],
        "close": [9.0, 10.0, 8.0, 12.5, 13.5, 10.5, 11.5, 9.0],
    })
    s = compute_swings(df, k=1)
    state, events = compute_structure(df, s)
    assert events == [(3, BOS_BULL), (7, CHOCH_BEAR)]
    assert list(state.iloc[:3]) == [NEUTRAL, NEUTRAL, NEUTRAL]
    assert list(state.iloc[3:7]) == [UP, UP, UP, UP]
    assert state.iloc[7] == DOWN
