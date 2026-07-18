"""HTF order-flow bias — DEF-BIAS-01.

Bias is derived from the 1H structure state (BOS/CHoCH engine, Phase 2):
  * state UP   -> BULLISH  (last event was a bullish BOS/CHoCH and price has not
                            closed below the last higher-low; a close below it
                            would itself flip the state via a bearish CHoCH)
  * state DOWN -> BEARISH
  * otherwise  -> NEUTRAL   (no trades)

``htf_bias_series`` computes the bias per HTF bar; ``bias_at`` resolves the bias
for an LTF timestamp using the most recent **fully-closed** HTF bar (no look-ahead).
"""
from __future__ import annotations

import pandas as pd

from ..indicators.structure import DOWN, UP, compute_structure
from ..indicators.swings import compute_swings
from ..tsutil import asof_closed

BULLISH, BEARISH, NEUTRAL = "BULLISH", "BEARISH", "NEUTRAL"

_MAP = {UP: BULLISH, DOWN: BEARISH}


def htf_bias_series(htf: pd.DataFrame, swing_k: int = 2) -> pd.Series:
    """Bias label per HTF bar (index = htf.index)."""
    swings = compute_swings(htf, k=swing_k)
    state, _ = compute_structure(htf, swings)
    return state.map(lambda s: _MAP.get(s, NEUTRAL)).rename("bias")


def bias_at(bias_series: pd.Series, ts) -> str:
    """Bias in force at LTF time ``ts`` — the last HTF bar that has fully closed.

    HTF bars are left-labelled/right-open, so a bar labelled T covers [T, T+1h).
    A bar is only usable once it has closed, i.e. its label is strictly before the
    LTF bar's open time.
    """
    return str(asof_closed(bias_series, ts, default=NEUTRAL))
