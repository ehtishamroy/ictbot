"""Draw on Liquidity — DEF-DOL-01.

A valid draw is the nearest UNSWEPT liquidity pool in the bias direction within
``reach x ATR(1H)`` of current price:
  * longs  -> an unswept PDH ABOVE price, within reach;
  * shorts -> an unswept PDL BELOW price, within reach.

No pool within reach => no target worth drawing to => no trade.
"""
from __future__ import annotations

import numpy as np

BULL, BEAR = "bull", "bear"


def dol_exists(
    price: float,
    level: float,
    atr_1h: float,
    direction: str,
    swept: bool,
    reach: float = 3.0,
) -> bool:
    """True if ``level`` is an unswept draw in ``direction`` within reach of price."""
    if swept or not np.isfinite(level) or not np.isfinite(atr_1h) or atr_1h <= 0:
        return False
    reach_px = reach * atr_1h
    if direction == BULL:
        return level > price and (level - price) <= reach_px
    if direction == BEAR:
        return level < price and (price - level) <= reach_px
    raise ValueError(f"bad direction: {direction!r}")
