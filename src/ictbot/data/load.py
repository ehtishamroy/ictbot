"""Data loading — CSV/tick -> UTC OHLCV frames for the harness.

Accepts a 1-minute (or finer) OHLCV CSV and builds the 1m/5m/1H frames the engine
and intrabar fill model need. Column names are matched flexibly; the timestamp is
parsed as UTC. Real backtests must use tick or 1-minute data (spec B1) — coarser
inputs are rejected.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from .resample import resample_ohlcv, ticks_to_bars

_TIME_CANDS = ["time", "timestamp", "date", "datetime", "gmt time"]
_OHLC = {"open": ["open", "o"], "high": ["high", "h"], "low": ["low", "l"],
         "close": ["close", "c"], "volume": ["volume", "vol", "v"]}


def _find(cols, cands):
    low = {c.lower(): c for c in cols}
    for cand in cands:
        if cand in low:
            return low[cand]
    return None


def load_ohlcv_csv(path: str | Path) -> pd.DataFrame:
    """Load a 1m OHLCV CSV into a UTC-indexed DataFrame (open/high/low/close[/volume])."""
    df = pd.read_csv(path)
    tcol = _find(df.columns, _TIME_CANDS)
    if tcol is None:
        raise ValueError(f"no timestamp column found in {list(df.columns)}")
    idx = pd.to_datetime(df[tcol], utc=True, errors="coerce")
    out = pd.DataFrame(index=pd.DatetimeIndex(idx, name="time"))
    for canon, cands in _OHLC.items():
        col = _find(df.columns, cands)
        if col is not None:
            out[canon] = df[col].to_numpy()
        elif canon != "volume":
            raise ValueError(f"missing required column {canon!r}")
    return out[~out.index.isna()].sort_index()


def build_frames(df1m: pd.DataFrame):
    """Return (df1m, df5, df1h) from a 1-minute OHLCV frame."""
    if df1m.index.tz is None:
        df1m = df1m.tz_localize("UTC")
    df5 = resample_ohlcv(df1m, "5min")
    df1h = resample_ohlcv(df1m, "1h")
    return df1m, df5, df1h


def frames_from_ticks(ticks: pd.DataFrame):
    """Return (df1m, df5, df1h) from a tick frame (bid/ask)."""
    df1m = ticks_to_bars(ticks, "1min")
    return build_frames(df1m)
