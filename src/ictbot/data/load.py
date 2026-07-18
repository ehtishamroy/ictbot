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


def load_histdata_ascii_m1(paths: list[str | Path]) -> pd.DataFrame:
    """Load HistData.com free 'Generic ASCII' M1 export(s) into UTC OHLCV.

    Format: no header, semicolon-separated ``YYYYMMDD HHMMSS;O;H;L;C;V`` (volume
    is always 0 in the free feed). HistData documents these timestamps as a
    **fixed GMT-5 ("EST") offset with NO Daylight Saving adjustment** — this is
    NOT the same as true ``America/New_York``, which shifts to UTC-4 in summer.
    Localizing naively as ``America/New_York`` would silently mislabel every
    summer bar by an hour: exactly the DST bug class the spec calls the #1
    cause of broken ICT backtests. So these are localized to the fixed
    ``Etc/GMT+5`` zone (POSIX sign is inverted: ``Etc/GMT+5`` == UTC-5) and
    converted to true UTC here, before any DST-aware killzone/PDH-PDL logic
    ever sees them. Multiple yearly files are concatenated and sorted.
    """
    frames = []
    for p in paths:
        df = pd.read_csv(p, sep=";", header=None,
                         names=["ts", "open", "high", "low", "close", "volume"])
        frames.append(df)
    raw = pd.concat(frames, ignore_index=True)
    ts = pd.to_datetime(raw["ts"], format="%Y%m%d %H%M%S")
    ts_utc = ts.dt.tz_localize("Etc/GMT+5").dt.tz_convert("UTC")
    out = raw[["open", "high", "low", "close", "volume"]].copy()
    out.index = pd.DatetimeIndex(ts_utc, name="time")
    return out[~out.index.duplicated()].sort_index()


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
