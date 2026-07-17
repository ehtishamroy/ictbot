"""Phase 3 — trigger detectors: FVG, sweep, displacement, MSS.

Every fixture's expected outcome is computed by hand from the DEF-ID definitions.
"""
import numpy as np
import pandas as pd

from ictbot.detectors.displacement import is_displacement
from ictbot.detectors.fvg import BULL, detect_fvg, find_fvgs, is_alive, pick_nested
from ictbot.detectors.mss import mss_confirmed
from ictbot.detectors.sweep import detect_sweep_at


def _df(rows):
    n = len(next(iter(rows.values())))
    idx = pd.date_range("2024-01-15 13:30", periods=n, freq="5min", tz="UTC")
    return pd.DataFrame(rows, index=idx)


# --- FVG ---------------------------------------------------------------------
def test_detect_bullish_fvg_and_size_band():
    highs = np.array([1.0000, 1.0010, 1.0020])
    lows = np.array([0.9990, 1.0002, 1.0008])   # gap 1.0000..1.0008, height 8 pips
    g = detect_fvg(highs, lows, 2, atr_value=0.001, fvg_min=0.5, fvg_max=3.0)
    assert g is not None and g.direction == BULL
    assert abs(g.bottom - 1.0000) < 1e-12 and abs(g.top - 1.0008) < 1e-12
    assert abs(g.ce - 1.0004) < 1e-9
    # too-small band: with atr 0.002, lo_band = 0.001 > 0.0008 height -> rejected
    assert detect_fvg(highs, lows, 2, atr_value=0.002, fvg_min=0.5, fvg_max=3.0) is None


def test_fvg_dies_when_fully_traded_through():
    highs = np.array([1.0000, 1.0010, 1.0020, 1.0021])
    lows = np.array([0.9990, 1.0002, 1.0008, 0.9999])   # bar 3 low pierces bottom 1.0000
    g = detect_fvg(highs, lows, 2, atr_value=0.001, fvg_min=0.5, fvg_max=3.0)
    assert is_alive(g, highs, lows, up_to=2) is True
    assert is_alive(g, highs, lows, up_to=3) is False


def test_pick_nested_lowest_bull():
    from ictbot.detectors.fvg import FVG
    a = FVG(BULL, 1.0000, 1.0006, 5)   # ce 1.0003
    b = FVG(BULL, 1.0010, 1.0016, 9)   # ce 1.0013
    assert pick_nested([a, b], BULL) is a


# --- Sweep -------------------------------------------------------------------
def test_bull_sweep_of_pdl():
    df = _df({
        "high": [1.0006, 1.0000, 1.0004],
        "low": [1.0005, 0.9995, 1.0001],
        "close": [1.0005, 0.9998, 1.0002],
    })
    s = detect_sweep_at(df, i=2, level=1.0000, direction="bull",
                        tick=0.00001, sweep_close_n=3)
    assert s is not None
    assert s.penetration_idx == 1 and s.close_back_idx == 2
    assert s.extreme == 0.9995
    # at bar 1 there is no close-back yet
    assert detect_sweep_at(df, 1, 1.0000, "bull", 0.00001, 3) is None


def test_no_closeback_is_void():
    df = _df({
        "high": [1.0006, 1.0000, 0.9998],
        "low": [1.0005, 0.9995, 0.9990],
        "close": [1.0005, 0.9998, 0.9996],   # keeps going down -> breakout
    })
    assert detect_sweep_at(df, 2, 1.0000, "bull", 0.00001, 3) is None


# --- Displacement ------------------------------------------------------------
def test_displacement_single_and_run_and_reject():
    df = _df({
        "open": [1.0000, 1.0001, 1.0010, 1.0000],
        "close": [1.0020, 1.0009, 1.0019, 1.0050],
        "high": [1.0021, 1.0010, 1.0020, 1.0051],
        "low": [0.9999, 1.0000, 1.0009, 0.9999],
    })
    atr = 0.001
    # bar 0: single body 0.0020 >= 1.5*atr(0.0015) -> displacement
    assert is_displacement(df, 0, atr, "bull", disp_mult=1.5)
    # bars 1-2: bodies 0.0008 + 0.0009 summed 0.0017 >= 0.0015 over a 2-run
    assert is_displacement(df, 2, atr, "bull", disp_mult=1.5)
    # bar 3: single body 0.0050 > 4*atr(0.004) -> news-print reject
    assert not is_displacement(df, 3, atr, "bull", disp_mult=1.5)
    # wrong direction
    assert not is_displacement(df, 0, atr, "bear", disp_mult=1.5)


# --- MSS (integration of the above) -----------------------------------------
def test_mss_bullish():
    df = _df({
        "open": [1.0000, 1.0001, 1.0012],
        "high": [1.0002, 1.0013, 1.0026],
        "low": [0.9998, 1.0000, 1.0010],
        "close": [1.0001, 1.0012, 1.0025],
    })
    atr = pd.Series([0.001, 0.001, 0.001], index=df.index)
    swing_high = 1.0010    # recent confirmed swing high; close 1.0025 breaks it
    g = mss_confirmed(df, atr, i=2, direction="bull", conf_swing_level=swing_high,
                      disp_mult=1.5, fvg_min=0.5, fvg_max=3.0)
    assert g is not None and g.direction == BULL
    assert g.bottom == 1.0002 and g.top == 1.0010
    # no sweep in window -> void
    assert mss_confirmed(df, atr, 2, "bull", swing_high, 1.5, 0.5,
                         sweep_within_window=False) is None
    # close does not exceed the swing high -> void
    assert mss_confirmed(df, atr, 2, "bull", 1.0030, 1.5, 0.5) is None
