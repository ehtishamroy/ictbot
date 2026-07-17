"""Market structure — DEF-STRUCT-01 (BOS) and DEF-STRUCT-02 (CHoCH).

Walks bars left-to-right maintaining a structure state (NEUTRAL/UP/DOWN) using
only swings confirmed as of each bar (from ``compute_swings``). Events fire on a
**close** (not a wick) beyond the most recent confirmed swing:

  * break above the active confirmed swing high -> bullish BOS if already UP/NEUTRAL,
    bullish CHoCH if currently DOWN (flips state to UP);
  * break below the active confirmed swing low -> bearish BOS if already DOWN/NEUTRAL,
    bearish CHoCH if currently UP (flips state to DOWN).

A swing level is "consumed" once broken and cannot re-fire until a newer swing of
that side confirms — so a run of closes above an already-broken high does not spam
BOS events. Wick-only breaks are ignored here (they are sweeps, handled elsewhere).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

NEUTRAL, UP, DOWN = "NEUTRAL", "UP", "DOWN"
BOS_BULL, BOS_BEAR = "BOS_BULL", "BOS_BEAR"
CHOCH_BULL, CHOCH_BEAR = "CHOCH_BULL", "CHOCH_BEAR"


def compute_structure(df: pd.DataFrame, swings: pd.DataFrame):
    """Return (state_series, events).

    ``state_series`` is the structure state per bar; ``events`` is a list of
    ``(bar_position, event_type)`` tuples.
    """
    close = df["close"].to_numpy(dtype=float)
    conf_sh = swings["conf_sh"].to_numpy(dtype=float)
    conf_sl = swings["conf_sl"].to_numpy(dtype=float)
    conf_sh_idx = swings["conf_sh_idx"].to_numpy(dtype=int)
    conf_sl_idx = swings["conf_sl_idx"].to_numpy(dtype=int)
    n = len(df)

    state = np.empty(n, dtype=object)
    events: list[tuple[int, str]] = []
    cur = NEUTRAL
    broken_sh_idx = -1
    broken_sl_idx = -1

    for t in range(n):
        sh, sh_idx = conf_sh[t], conf_sh_idx[t]
        sl, sl_idx = conf_sl[t], conf_sl_idx[t]
        c = close[t]

        broke_high = sh_idx >= 0 and sh_idx != broken_sh_idx and not np.isnan(sh) and c > sh
        broke_low = sl_idx >= 0 and sl_idx != broken_sl_idx and not np.isnan(sl) and c < sl

        if broke_high:
            events.append((t, CHOCH_BULL if cur == DOWN else BOS_BULL))
            cur = UP
            broken_sh_idx = sh_idx
        elif broke_low:
            events.append((t, CHOCH_BEAR if cur == UP else BOS_BEAR))
            cur = DOWN
            broken_sl_idx = sl_idx

        state[t] = cur

    return pd.Series(state, index=df.index, name="state"), events
