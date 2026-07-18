"""Small time-series alignment helpers shared across detectors and the engine."""
from __future__ import annotations

import pandas as pd


def asof_closed(series: pd.Series, ts, default=None):
    """Value of the last bar whose (left) label is strictly before ``ts``.

    Bars are left-labelled/right-open, so a bar labelled T is only usable once
    ``ts`` has passed T's close — i.e. label < ts. This is the no-look-ahead way
    to read an HTF series (bias, ATR) from an LTF timestamp.
    """
    ts = pd.Timestamp(ts)
    idx = series.index
    if idx.tz is not None:
        ts = ts.tz_localize(idx.tz) if ts.tzinfo is None else ts.tz_convert(idx.tz)
    pos = idx.searchsorted(ts, side="left") - 1
    if pos < 0:
        return default
    return series.iloc[pos]
