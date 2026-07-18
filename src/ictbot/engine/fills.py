"""Fill models — how intrabar events are resolved (spec D3 look-ahead rules).

The state machine asks a ``FillModel`` three questions per 5m bar:
  * ``pre_tp1``  -> 'SL' | 'TP1' | None   (before the first partial)
  * ``post_tp1`` -> 'SL' | 'TP2' | None   (after TP1, stop at break-even)
  * ``wait``     -> 'FILL' | 'TP1_FIRST' | 'NONE'  (limit still resting)

``BarFillModel`` (default) uses only the 5m bar and resolves same-bar ambiguity
conservatively (STOP assumed first; FILL assumed before a same-bar TP reach).

``IntrabarFillModel`` walks the 1-minute sub-bars of each 5m bar in time order and
returns the FIRST event that actually happens — the spec-mandated way to answer
"which came first, the stop or the target?" without a 5m same-bar guess. A limit
still only counts as filled on a trade-through by >= 1 tick.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

LONG, SHORT = "long", "short"


class BarFillModel:
    """Conservative 5m-only fill model (no intrabar data)."""

    def pre_tp1(self, ts, hi, lo, entry, sl, tp1, direction):
        if direction == LONG:
            if lo <= sl:
                return "SL"
            if hi >= tp1:
                return "TP1"
        else:
            if hi >= sl:
                return "SL"
            if lo <= tp1:
                return "TP1"
        return None

    def post_tp1(self, ts, hi, lo, entry, sl, tp2, direction):
        if direction == LONG:
            if lo <= sl:
                return "SL"
            if hi >= tp2:
                return "TP2"
        else:
            if hi >= sl:
                return "SL"
            if lo <= tp2:
                return "TP2"
        return None

    def wait(self, ts, hi, lo, ce, tp1, tick, direction):
        if direction == LONG:
            filled, reached = lo <= ce - tick, hi >= tp1
        else:
            filled, reached = hi >= ce + tick, lo <= tp1
        if filled:
            return "FILL"
        if reached:
            return "TP1_FIRST"
        return "NONE"


class IntrabarFillModel:
    """1-minute intrabar resolution; falls back to the bar model where 1m is absent."""

    def __init__(self, df1m: pd.DataFrame):
        self._bar = BarFillModel()
        floor = df1m.index.floor("5min")
        self._groups: dict = {}
        for ts, sub in df1m.groupby(floor):
            self._groups[pd.Timestamp(ts)] = (
                sub["high"].to_numpy(float),
                sub["low"].to_numpy(float),
            )

    def _sub(self, ts):
        return self._groups.get(pd.Timestamp(ts))

    def pre_tp1(self, ts, hi, lo, entry, sl, tp1, direction):
        sub = self._sub(ts)
        if sub is None:
            return self._bar.pre_tp1(ts, hi, lo, entry, sl, tp1, direction)
        mh, ml = sub
        for k in range(len(mh)):
            if direction == LONG:
                if ml[k] <= sl:
                    return "SL"
                if mh[k] >= tp1:
                    return "TP1"
            else:
                if mh[k] >= sl:
                    return "SL"
                if ml[k] <= tp1:
                    return "TP1"
        return None

    def post_tp1(self, ts, hi, lo, entry, sl, tp2, direction):
        sub = self._sub(ts)
        if sub is None:
            return self._bar.post_tp1(ts, hi, lo, entry, sl, tp2, direction)
        mh, ml = sub
        for k in range(len(mh)):
            if direction == LONG:
                if ml[k] <= sl:
                    return "SL"
                if mh[k] >= tp2:
                    return "TP2"
            else:
                if mh[k] >= sl:
                    return "SL"
                if ml[k] <= tp2:
                    return "TP2"
        return None

    def wait(self, ts, hi, lo, ce, tp1, tick, direction):
        sub = self._sub(ts)
        if sub is None:
            return self._bar.wait(ts, hi, lo, ce, tp1, tick, direction)
        mh, ml = sub
        for k in range(len(mh)):
            if direction == LONG:
                if ml[k] <= ce - tick:
                    return "FILL"
                if mh[k] >= tp1:
                    return "TP1_FIRST"
            else:
                if mh[k] >= ce + tick:
                    return "FILL"
                if ml[k] <= tp1:
                    return "TP1_FIRST"
        return "NONE"
