"""Forward-test tracker for DIVTREND (go-live ladder, Part E).

Records each monthly rebalance's target weights to a log, then — as new price
data arrives — computes the REALIZED forward return of those held weights and
compares it to the backtest, with a hard kill-switch: if forward drawdown exceeds
``kill_mult`` x the backtest max drawdown, SUSPEND and go back to research.
A forward test is meaningful only over months; short logs are reported as such.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from .metrics import compute_metrics

# backtest reference (DIVTREND_v1.0_findings.md — honest full-period figures)
BACKTEST_SHARPE = 0.67
BACKTEST_MAXDD_PCT = 19.2
KILL_MULT = 1.5


def append_forward_log(path: str | Path, asof: pd.Timestamp, weights: pd.Series) -> list:
    """Append (or replace) this rebalance's target weights in the JSON log."""
    path = Path(path)
    log = json.loads(path.read_text()) if path.exists() else []
    key = str(pd.Timestamp(asof).date())
    log = [e for e in log if e["date"] != key]
    log.append({"date": key, "weights": {k: float(v) for k, v in weights.items()
                                         if abs(v) > 1e-9}})
    log.sort(key=lambda e: e["date"])
    path.write_text(json.dumps(log, indent=2))
    return log


def realized_forward_returns(prices: pd.DataFrame, log: list) -> pd.Series:
    """Daily portfolio returns from holding each logged weight set until the next
    rebalance date, using actual subsequent prices. Empty until >= 2 log dates
    with price data beyond the first."""
    if len(log) < 1:
        return pd.Series(dtype=float)
    rets = prices.pct_change()
    pieces = []
    dates = [pd.Timestamp(e["date"]) for e in log]
    for i, e in enumerate(log):
        start = pd.Timestamp(e["date"])
        end = dates[i + 1] if i + 1 < len(log) else prices.index[-1]
        w = pd.Series(e["weights"])
        seg = rets.loc[(rets.index > start) & (rets.index <= end)]
        if seg.empty:
            continue
        cols = [c for c in w.index if c in seg.columns]
        pieces.append((seg[cols] * w[cols]).sum(axis=1))
    if not pieces:
        return pd.Series(dtype=float)
    return pd.concat(pieces).sort_index()


def evaluate_forward(prices: pd.DataFrame, log: list) -> dict:
    """Forward performance vs backtest + kill-switch verdict."""
    fwd = realized_forward_returns(prices, log)
    n = len(fwd)
    if n < 20:
        return {"status": "TOO_SHORT", "days": n,
                "message": f"only {n} forward days logged — need a few months to judge."}
    m = compute_metrics(fwd)
    nav = (1 + fwd).cumprod()
    dd_pct = abs((nav / nav.cummax() - 1).min()) * 100
    cum_ret = float(nav.iloc[-1] - 1)
    killed = bool(dd_pct > KILL_MULT * BACKTEST_MAXDD_PCT)
    if killed:
        status = "SUSPEND"
    elif m.sharpe < 0 and n > 126:      # ~6 months of clearly negative forward
        status = "WARN_NEGATIVE"
    else:
        status = "ON_TRACK"
    return {
        "status": status, "days": n, "months_approx": round(n / 21, 1),
        "fwd_sharpe": round(m.sharpe, 2), "fwd_return_pct": round(cum_ret * 100, 1),
        "fwd_maxdd_pct": round(dd_pct, 1),
        "backtest_sharpe": BACKTEST_SHARPE, "backtest_maxdd_pct": BACKTEST_MAXDD_PCT,
        "kill_threshold_pct": round(KILL_MULT * BACKTEST_MAXDD_PCT, 1),
        "killed": killed,
    }


def format_forward(ev: dict) -> str:
    if ev["status"] == "TOO_SHORT":
        return f"Forward test: {ev['message']}"
    lines = [
        f"Forward test — {ev['months_approx']} months ({ev['days']} days) logged",
        f"  Forward Sharpe  : {ev['fwd_sharpe']}   (backtest {ev['backtest_sharpe']})",
        f"  Forward return  : {ev['fwd_return_pct']:+}%",
        f"  Forward maxDD   : {ev['fwd_maxdd_pct']}%   (kill-switch at {ev['kill_threshold_pct']}%)",
        f"  VERDICT: {ev['status']}",
    ]
    if ev["status"] == "SUSPEND":
        lines.append("  >> Drawdown breached the kill-switch. STOP paper-trading; back to research.")
    elif ev["status"] == "WARN_NEGATIVE":
        lines.append("  >> ~6+ months of negative forward Sharpe. Investigate before continuing.")
    elif ev["status"] == "ON_TRACK":
        lines.append("  >> Behaving within expectations. Keep logging monthly.")
    return "\n".join(lines)
