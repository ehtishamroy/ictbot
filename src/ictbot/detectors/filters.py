"""Entry filters — spread and news (spec A5 #1/#2, D5).

* ``spread_ok``: reject when spread at order placement exceeds ``max_spread_pips``.
* ``news_clear``: reject a NEW entry within +/- ``window_min`` of a high-impact
  USD/EUR event. Open positions are NOT flattened (news_flat = false). The event
  list is supplied by the caller (live: MQL5 calendar; backtest: ForexFactory CSV)
  so the filter is always testable — an untestable filter is a discretionary one.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

PIP = 0.0001  # EURUSD


def spread_ok(spread_price: float, max_spread_pips: float, pip: float = PIP) -> bool:
    """True if the current spread (in price) is within the cap."""
    if not np.isfinite(spread_price):
        return False
    return spread_price <= max_spread_pips * pip


def news_clear(ts, events, window_min: int = 15) -> bool:
    """True if no high-impact event falls within +/- ``window_min`` of ``ts``.

    ``events`` is an iterable of UTC timestamps (already filtered to USD/EUR
    high-impact by the loader).
    """
    ts = pd.Timestamp(ts)
    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")
    window = pd.Timedelta(minutes=window_min)
    for e in events:
        e = pd.Timestamp(e)
        if e.tzinfo is None:
            e = e.tz_localize("UTC")
        if abs(e - ts) <= window:
            return False
    return True
