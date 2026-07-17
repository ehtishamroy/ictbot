"""Market Structure Shift — DEF-MSS-01.

At bar ``i``, a bullish MSS requires ALL of:
  1. a sweep occurred within the last ``mss_window`` LTF candles (tracked by the
     engine, passed in as ``sweep_within_window``);
  2. the candle CLOSES beyond the most recent confirmed opposite swing
     (above the confirmed swing HIGH for bull; below the swing LOW for bear);
  3. the breaking move qualifies as DEF-DISP-01 AND leaves at least one valid FVG.

Returns the FVG to trade (nested rule: lowest bullish / highest bearish), or None.
The FVG search spans the displacement window ending at ``i``.
"""
from __future__ import annotations

import pandas as pd

from .displacement import is_displacement
from .fvg import BEAR, BULL, FVG, find_fvgs, is_alive, pick_nested


def mss_confirmed(
    df: pd.DataFrame,
    atr: pd.Series,
    i: int,
    direction: str,
    conf_swing_level: float,
    disp_mult: float,
    fvg_min: float,
    fvg_max: float = 3.0,
    disp_max: float = 4.0,
    max_run: int = 3,
    sweep_within_window: bool = True,
) -> FVG | None:
    """Return the entry FVG if a valid MSS in ``direction`` completes at bar ``i``."""
    if not sweep_within_window:
        return None
    if conf_swing_level is None or pd.isna(conf_swing_level):
        return None

    close_i = float(df["close"].to_numpy(dtype=float)[i])
    # (2) close beyond the most recent confirmed opposite swing
    if direction == BULL:
        if not (close_i > conf_swing_level):
            return None
    elif direction == BEAR:
        if not (close_i < conf_swing_level):
            return None
    else:
        raise ValueError(f"bad direction: {direction!r}")

    # (3a) displacement into the break
    if not is_displacement(df, i, atr.to_numpy(dtype=float)[i], direction,
                           disp_mult, disp_max, max_run):
        return None

    # (3b) the move must leave >= 1 valid FVG; pick per the nested rule
    start = max(2, i - max_run)
    candidates = [
        g for g in find_fvgs(df, atr, start, i, direction, fvg_min, fvg_max)
        if is_alive(g, df["high"].to_numpy(dtype=float),
                    df["low"].to_numpy(dtype=float), i)
    ]
    return pick_nested(candidates, direction)
