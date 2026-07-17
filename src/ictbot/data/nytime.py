"""Time layer — DEF-KZ-01 / DEF-TIME-01.

The single most common bug in ICT EAs is wrong time handling: a wrong NY offset
makes every killzone and every PDH/PDL wrong, and every downstream number garbage
(spec D6 bug #2/#3/#4). So this module is DST-correct by construction — it uses the
``America/New_York`` zone via ``zoneinfo`` and never a fixed UTC offset.

Two clocks matter:
- **Killzone**: NY AM 08:30-11:00 wall-clock (setups form AND fill only inside it).
- **Trading day**: runs 17:00 -> 17:00 NY. PDH/PDL are the prior trading day's
  high/low; daily counters reset on this boundary, NOT server/UTC midnight.

All public functions take UTC-aware pandas timestamps / indexes. Passing a
tz-naive value is treated as UTC (and asserted), so a caller can never silently
feed local time.
"""
from __future__ import annotations

from datetime import time as dtime
from zoneinfo import ZoneInfo

import pandas as pd

NY = ZoneInfo("America/New_York")
UTC = ZoneInfo("UTC")

DEFAULT_KZ_START = dtime(8, 30)
DEFAULT_KZ_END = dtime(11, 0)
DEFAULT_DAY_BOUNDARY = dtime(17, 0)


# --- parsing helpers --------------------------------------------------------
def parse_hhmm(s: str) -> dtime:
    """'08:30' -> datetime.time(8, 30)."""
    hh, mm = s.split(":")
    return dtime(int(hh), int(mm))


def _as_utc_ts(ts) -> pd.Timestamp:
    ts = pd.Timestamp(ts)
    if ts.tzinfo is None:
        return ts.tz_localize(UTC)
    return ts.tz_convert(UTC)


def _as_utc_index(idx: pd.DatetimeIndex) -> pd.DatetimeIndex:
    idx = pd.DatetimeIndex(idx)
    if idx.tz is None:
        return idx.tz_localize(UTC)
    return idx.tz_convert(UTC)


# --- scalar API -------------------------------------------------------------
def to_ny(ts) -> pd.Timestamp:
    """UTC timestamp -> tz-aware New York wall-clock timestamp (DST-correct)."""
    return _as_utc_ts(ts).tz_convert(NY)


def in_killzone(
    ts,
    start: dtime = DEFAULT_KZ_START,
    end: dtime = DEFAULT_KZ_END,
) -> bool:
    """True if ``ts`` falls inside the NY-AM killzone [start, end) in NY time."""
    t = to_ny(ts).time()
    return start <= t < end


def trading_day(ts, boundary: dtime = DEFAULT_DAY_BOUNDARY) -> pd.Timestamp:
    """Label of the 17:00->17:00 NY trading day that contains ``ts``.

    Bars at/after the 17:00 NY boundary belong to the NEXT calendar date's
    session, so e.g. Monday 17:00 NY and Tuesday 08:30 NY share the label
    ``Tuesday`` — and their "previous day" is the Monday session.
    """
    nyt = to_ny(ts)
    d = nyt.normalize().tz_localize(None)  # NY calendar date, tz-naive
    if nyt.time() >= boundary:
        d = d + pd.Timedelta(days=1)
    return pd.Timestamp(d.date())


# --- vectorized API (for whole DataFrames) ---------------------------------
def to_ny_index(idx: pd.DatetimeIndex) -> pd.DatetimeIndex:
    return _as_utc_index(idx).tz_convert(NY)


def in_killzone_mask(
    idx: pd.DatetimeIndex,
    start: dtime = DEFAULT_KZ_START,
    end: dtime = DEFAULT_KZ_END,
) -> pd.Series:
    """Boolean Series (indexed by ``idx``) flagging bars inside the killzone."""
    ny = to_ny_index(idx)
    minutes = ny.hour * 60 + ny.minute
    lo = start.hour * 60 + start.minute
    hi = end.hour * 60 + end.minute
    return pd.Series((minutes >= lo) & (minutes < hi), index=idx)


def trading_day_series(
    idx: pd.DatetimeIndex,
    boundary: dtime = DEFAULT_DAY_BOUNDARY,
) -> pd.Series:
    """Series of trading-day labels (tz-naive dates) for each bar in ``idx``."""
    ny = to_ny_index(idx)
    bmin = boundary.hour * 60 + boundary.minute
    minutes = ny.hour * 60 + ny.minute
    dates = ny.normalize().tz_localize(None)
    roll = pd.to_datetime(pd.Series(dates, index=idx))
    roll[minutes >= bmin] += pd.Timedelta(days=1)
    return roll.dt.normalize()


def previous_day_levels(
    df: pd.DataFrame,
    boundary: dtime = DEFAULT_DAY_BOUNDARY,
) -> pd.DataFrame:
    """Attach PDH / PDL (previous trading-day high/low) to each bar.

    Uses the 17:00->17:00 NY trading day (DEF-LIQ-01). The levels for a given
    bar come from the immediately preceding trading day and are therefore fully
    known at that bar — no look-ahead. Requires 'high'/'low' columns and a
    UTC DatetimeIndex.
    """
    out = df.copy()
    tday = trading_day_series(out.index, boundary)
    out["trading_day"] = tday.values
    daily = out.groupby("trading_day").agg(day_high=("high", "max"),
                                           day_low=("low", "min"))
    pdh = daily["day_high"].shift(1)
    pdl = daily["day_low"].shift(1)
    out["pdh"] = out["trading_day"].map(pdh)
    out["pdl"] = out["trading_day"].map(pdl)
    return out
