"""Live/forward position generation for DIVTREND.

Computes the strategy's target weights as of a given date (default: the latest
bar) using the SAME signal + sizing as the backtester, and formats a plain
position sheet a person can paper-trade. This is the monthly "what do I hold"
output for the forward test — no new logic, just the locked rules evaluated now.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .params import DivtrendParams
from .signal import tsmom_signs
from .sizing import estimate_cov, target_weights


def weights_asof(prices: pd.DataFrame, params: DivtrendParams, sleeves: dict,
                 d: int | None = None) -> pd.Series:
    """Target weight per instrument as of price-row ``d`` (default last row)."""
    prices = prices.sort_index()
    tickers = list(prices.columns)
    arr = prices.to_numpy(float)
    n = len(arr)
    if d is None:
        d = n - 1
    ret = np.zeros_like(arr)
    with np.errstate(invalid="ignore", divide="ignore"):
        ret[1:] = arr[1:] / arr[:-1] - 1.0
    ret = np.where(np.isfinite(ret), ret, 0.0)

    warmup = max((params.lookback_months + params.skip_recent_month) * params.month_days,
                 params.vol_lookback_days) + 1
    if d < warmup:
        return pd.Series(0.0, index=tickers)

    signs = tsmom_signs(arr, d, params.lookback_months,
                        params.skip_recent_month, params.month_days)
    win = ret[d - params.vol_lookback_days + 1: d + 1]
    cov, vol = estimate_cov(win, params.trading_days_year)
    sleeve_ids = np.array([hash(sleeves.get(t, "other")) for t in tickers])
    w = target_weights(signs, vol, cov, sleeve_ids, params)
    return pd.Series(w, index=tickers)


def position_sheet(prices: pd.DataFrame, params: DivtrendParams,
                   sleeves: dict) -> pd.DataFrame:
    """Human-readable target positions as of the latest bar."""
    w = weights_asof(prices, params, sleeves)
    rows = []
    for t in w.index:
        wt = float(w[t])
        if abs(wt) < 1e-6:
            side = "FLAT"
        else:
            side = "LONG" if wt > 0 else "SHORT"
        rows.append({"ticker": t, "sleeve": sleeves.get(t, "other"),
                     "side": side, "weight_pct": round(wt * 100, 1)})
    df = pd.DataFrame(rows).sort_values(["sleeve", "ticker"]).reset_index(drop=True)
    return df


def format_sheet(df: pd.DataFrame, asof: pd.Timestamp) -> str:
    active = df[df["side"] != "FLAT"]
    gross = df["weight_pct"].abs().sum()
    net = df["weight_pct"].sum()
    lines = [
        f"DIVTREND position sheet — as of {pd.Timestamp(asof).date()}",
        f"(gross exposure {gross:.0f}% of equity, net {net:+.0f}%; "
        f"{(active['side']=='LONG').sum()} long / {(active['side']=='SHORT').sum()} short)",
        "",
        f"{'TICKER':7}{'SLEEVE':11}{'SIDE':6}{'WEIGHT':>8}",
    ]
    for _, r in df.iterrows():
        mark = "" if r["side"] != "FLAT" else "  (no position)"
        lines.append(f"{r['ticker']:7}{r['sleeve']:11}{r['side']:6}{r['weight_pct']:>7.1f}%{mark}")
    lines += [
        "",
        "How to read: weight = % of account notional. LONG=buy, SHORT=sell short.",
        "Gross can exceed 100% (leverage, capped at k_max). Shorts need a margin",
        "account live; for the paper forward test just record them. Rebalance monthly.",
    ]
    return "\n".join(lines)
