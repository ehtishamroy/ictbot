"""Liquidity sweep — DEF-SWEEP-01.

A sweep of a level (PDL for longs, PDH for shorts) requires ALL of:
  1. price trades >= 1 tick beyond the level (a wick counts),
  2. within ``sweep_close_n`` candles of the first penetration, a candle CLOSES
     back on the original side,
  3. ``sweep_extreme`` = the most extreme price reached across the sweep (anchors
     the stop-loss).

No close-back inside the window => a breakout, not a sweep => the setup is void.

``detect_sweep_at`` is evaluated per bar: it asks "did a valid sweep of ``level``
complete with its close-back on bar ``i``?" and, if so, returns the sweep extreme.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

BULL, BEAR = "bull", "bear"


@dataclass(frozen=True)
class Sweep:
    direction: str        # 'bull' (swept PDL) | 'bear' (swept PDH)
    penetration_idx: int  # first bar to pierce the level
    close_back_idx: int   # bar that closed back on the original side
    extreme: float        # sweep_extreme (min low for bull, max high for bear)


def detect_sweep_at(
    df: pd.DataFrame,
    i: int,
    level: float,
    direction: str,
    tick: float,
    sweep_close_n: int,
) -> Sweep | None:
    """Return a ``Sweep`` if bar ``i`` is the close-back of a valid sweep, else None.

    ``direction='bull'`` sweeps liquidity BELOW ``level`` (PDL) and needs a close
    back ABOVE it; ``'bear'`` is the mirror (above PDH, close back below).
    """
    return sweep_at_arrays(
        df["high"].to_numpy(dtype=float),
        df["low"].to_numpy(dtype=float),
        df["close"].to_numpy(dtype=float),
        i, level, direction, tick, sweep_close_n,
    )


def sweep_at_arrays(
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    i: int,
    level: float,
    direction: str,
    tick: float,
    sweep_close_n: int,
) -> Sweep | None:
    """Array-based core of :func:`detect_sweep_at` (no per-call conversions)."""
    if i < 1 or not np.isfinite(level):
        return None

    if direction == BULL:
        if not (closes[i] > level):                 # must close back above
            return None
        # earliest penetration within the window that hasn't already closed back
        lo = max(0, i - sweep_close_n)
        pen = None
        for j in range(lo, i + 1):
            if lows[j] <= level - tick:
                pen = j
                break
        if pen is None:
            return None
        # bar i must be the FIRST close-back after the penetration
        if np.any(closes[pen:i] > level):
            return None
        extreme = float(np.min(lows[pen:i + 1]))
        return Sweep(BULL, pen, i, extreme)

    if direction == BEAR:
        if not (closes[i] < level):                 # must close back below
            return None
        lo = max(0, i - sweep_close_n)
        pen = None
        for j in range(lo, i + 1):
            if highs[j] >= level + tick:
                pen = j
                break
        if pen is None:
            return None
        if np.any(closes[pen:i] < level):
            return None
        extreme = float(np.max(highs[pen:i + 1]))
        return Sweep(BEAR, pen, i, extreme)

    raise ValueError(f"bad direction: {direction!r}")
