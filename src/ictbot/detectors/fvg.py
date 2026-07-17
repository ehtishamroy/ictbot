"""Fair Value Gap — DEF-FVG-01.

A 3-candle imbalance:
  * Bullish: ``low(c3) > high(c1)`` -> zone ``[high(c1), low(c3)]``
  * Bearish: ``high(c3) < low(c1)`` -> zone ``[high(c3), low(c1)]``

``CE`` (consequent encroachment) = 50% midpoint = the limit-entry level. A gap is
valid only if its height is within ``[fvg_min, fvg_max] x ATR``. A gap is DEAD once
price has traded through 100% of it (reached the far edge) and is never reused.

Nested-FVG rule (deterministic so chart and code always agree): when a move leaves
several valid gaps, use the **lowest bullish** / **highest bearish** — keyed by CE.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

BULL, BEAR = "bull", "bear"


@dataclass(frozen=True)
class FVG:
    direction: str      # 'bull' | 'bear'
    bottom: float       # lower edge (price)
    top: float          # upper edge (price)
    formed_idx: int     # bar position of c3 (the gap is known once c3 closes)

    @property
    def ce(self) -> float:
        return (self.top + self.bottom) / 2.0

    @property
    def height(self) -> float:
        return self.top - self.bottom


def detect_fvg(
    highs: np.ndarray,
    lows: np.ndarray,
    i: int,
    atr_value: float,
    fvg_min: float,
    fvg_max: float = 3.0,
) -> FVG | None:
    """FVG formed by candles (i-2, i-1, i), or None. Needs i >= 2 and a size fit."""
    if i < 2 or not np.isfinite(atr_value) or atr_value <= 0:
        return None
    lo_band, hi_band = fvg_min * atr_value, fvg_max * atr_value

    # bullish gap: gap between high of c1 and low of c3
    if lows[i] > highs[i - 2]:
        bottom, top = highs[i - 2], lows[i]
        if lo_band <= (top - bottom) <= hi_band:
            return FVG(BULL, float(bottom), float(top), i)
    # bearish gap
    if highs[i] < lows[i - 2]:
        bottom, top = highs[i], lows[i - 2]
        if lo_band <= (top - bottom) <= hi_band:
            return FVG(BEAR, float(bottom), float(top), i)
    return None


def is_alive(fvg: FVG, highs: np.ndarray, lows: np.ndarray, up_to: int) -> bool:
    """True unless price has traded through 100% of the gap by bar ``up_to``.

    Bullish gaps die when price reaches the bottom edge; bearish when it reaches
    the top edge. Bars strictly after formation are considered.
    """
    if up_to <= fvg.formed_idx:
        return True
    if fvg.direction == BULL:
        return not np.any(lows[fvg.formed_idx + 1: up_to + 1] <= fvg.bottom)
    return not np.any(highs[fvg.formed_idx + 1: up_to + 1] >= fvg.top)


def find_fvgs(
    df: pd.DataFrame,
    atr: pd.Series,
    start: int,
    end: int,
    direction: str,
    fvg_min: float,
    fvg_max: float = 3.0,
) -> list[FVG]:
    """All valid FVGs of ``direction`` with c3 in [start, end] (inclusive)."""
    highs = df["high"].to_numpy(dtype=float)
    lows = df["low"].to_numpy(dtype=float)
    atr_v = atr.to_numpy(dtype=float)
    out: list[FVG] = []
    for i in range(max(2, start), min(end, len(df) - 1) + 1):
        g = detect_fvg(highs, lows, i, atr_v[i], fvg_min, fvg_max)
        if g is not None and g.direction == direction:
            out.append(g)
    return out


def pick_nested(fvgs: list[FVG], direction: str) -> FVG | None:
    """Nested-FVG rule: lowest bullish (min CE) / highest bearish (max CE)."""
    if not fvgs:
        return None
    if direction == BULL:
        return min(fvgs, key=lambda g: g.ce)
    return max(fvgs, key=lambda g: g.ce)
