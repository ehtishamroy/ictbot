"""Feature builder — precomputes every look-ahead-safe column the engine reads.

Given the 5m LTF frame and the 1H HTF frame, attaches: ATR(5m), confirmed swings,
PDH/PDL + trading-day label, killzone flag, HTF bias (aligned to the last closed
1H bar), and ATR(1H) (same alignment). Kept separate from the state machine so the
same features can feed the backtest harness (Phase 5) and diagnostics.
"""
from __future__ import annotations

import pandas as pd

from ..data.nytime import in_killzone_mask, previous_day_levels
from ..detectors.bias import htf_bias_series
from ..indicators.atr import atr
from ..indicators.swings import compute_swings
from ..tsutil import asof_closed
from .params import EngineParams


def prepare_features(
    df5: pd.DataFrame,
    df1h: pd.DataFrame,
    params: EngineParams,
    default_spread_price: float | None = None,
) -> pd.DataFrame:
    """Return a 5m frame enriched with all engine inputs."""
    out = df5.copy()
    out["atr"] = atr(df5, params.atr_len)

    swings = compute_swings(df5, params.swing_k_ltf)
    out = out.join(swings)

    lv = previous_day_levels(df5, params.day_boundary)
    out["trading_day"] = lv["trading_day"].values
    out["pdh"] = lv["pdh"].values
    out["pdl"] = lv["pdl"].values

    out["in_kz"] = in_killzone_mask(df5.index, params.kz_start, params.kz_end).values

    bias_ser = htf_bias_series(df1h, params.swing_k_htf)
    atr1h_ser = atr(df1h, params.atr_len)
    out["bias"] = [asof_closed(bias_ser, ts, default="NEUTRAL") for ts in df5.index]
    out["atr1h"] = [asof_closed(atr1h_ser, ts, default=float("nan")) for ts in df5.index]

    if "spread" not in out.columns:
        if default_spread_price is None:
            default_spread_price = params.max_spread_price  # conservative fallback
        out["spread"] = default_spread_price

    return out
