"""Resampling — ticks -> OHLCV bars, and LTF -> HTF.

Bars are labelled by their **left/open edge** and are right-open, so a bar
timestamped 08:30 covers [08:30, 08:35) and is only complete once the next bar
opens. Downstream code must treat the current forming bar as incomplete (no
look-ahead). Mid price = (bid+ask)/2 is used for OHLC; per-bar mean spread is
kept so the cost model and the spread filter (A5) have real data to use.
"""
from __future__ import annotations

import pandas as pd

_OHLCV_COLS = ["open", "high", "low", "close", "volume"]


def ticks_to_bars(ticks: pd.DataFrame, freq: str = "1min") -> pd.DataFrame:
    """Aggregate a tick frame (bid/ask/…) into mid-price OHLCV bars.

    Adds ``spread`` (mean ask-bid, in price) per bar. Empty bars (market gaps)
    are dropped rather than forward-filled.
    """
    if ticks.empty:
        return pd.DataFrame(columns=_OHLCV_COLS + ["spread"])
    mid = (ticks["bid"] + ticks["ask"]) / 2.0
    spread = ticks["ask"] - ticks["bid"]
    vol = ticks.get("bid_vol", pd.Series(1.0, index=ticks.index)) + \
        ticks.get("ask_vol", pd.Series(0.0, index=ticks.index))
    frame = pd.DataFrame({"mid": mid, "spread": spread, "volume": vol})
    agg = frame.resample(freq, label="left", closed="left").agg(
        open=("mid", "first"),
        high=("mid", "max"),
        low=("mid", "min"),
        close=("mid", "last"),
        volume=("volume", "sum"),
        spread=("spread", "mean"),
    )
    return agg.dropna(subset=["open"])


def resample_ohlcv(bars: pd.DataFrame, freq: str) -> pd.DataFrame:
    """Aggregate existing OHLCV bars up to a higher timeframe (e.g. 5m -> 1H)."""
    if bars.empty:
        return bars.copy()
    agg_map = {
        "open": ("open", "first"),
        "high": ("high", "max"),
        "low": ("low", "min"),
        "close": ("close", "last"),
    }
    if "volume" in bars:
        agg_map["volume"] = ("volume", "sum")
    if "spread" in bars:
        agg_map["spread"] = ("spread", "mean")
    out = bars.resample(freq, label="left", closed="left").agg(**agg_map)
    return out.dropna(subset=["open"])
