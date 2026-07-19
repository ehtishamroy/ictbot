"""DIVTREND portfolio backtester (daily NAV, monthly rebalance).

Fixed target weights are set at each month-end and held to the next rebalance
(standard monthly-strategy approximation). Costs are charged on the traded weight
delta on rebalance days only; a no-trade band suppresses churn from small vol
wiggles. Output is a daily NET-return Series (the unit of analysis for Part-B
metrics) plus turnover and the weight history.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .params import DivtrendParams
from .signal import tsmom_signs
from .sizing import estimate_cov, target_weights


def month_end_positions(index: pd.DatetimeIndex) -> np.ndarray:
    """Integer positions of the last row in each calendar month."""
    per = pd.PeriodIndex(index, freq="M")
    is_last = np.empty(len(index), dtype=bool)
    is_last[:-1] = per[:-1] != per[1:]
    is_last[-1] = True
    return np.flatnonzero(is_last)


def run_divtrend(prices: pd.DataFrame, params: DivtrendParams, sleeves: dict,
                 cost_bps: dict | None = None, cost_mult: float = 1.0) -> dict:
    """Run the strategy; return dict(daily_ret, turnover_ann, weights, rebal_dates).

    ``cost_mult`` scales all costs (for the 1.5x/2.0x cost-stress gate).
    """
    prices = prices.sort_index()
    tickers = list(prices.columns)
    price_arr = prices.to_numpy(float)
    n, m = price_arr.shape

    ret = np.zeros((n, m))
    with np.errstate(invalid="ignore", divide="ignore"):
        ret[1:] = price_arr[1:] / price_arr[:-1] - 1.0
    ret = np.where(np.isfinite(ret), ret, 0.0)

    sleeve_ids = np.array([hash(sleeves.get(t, "other")) for t in tickers])
    cost_frac = np.array([(cost_bps or {}).get(t, params.default_cost_bps) * 1e-4
                          for t in tickers]) * cost_mult

    rebal = set(month_end_positions(prices.index).tolist())
    warmup = max((params.lookback_months + params.skip_recent_month) * params.month_days,
                 params.vol_lookback_days) + 1

    w_held = np.zeros(m)
    port_ret = np.zeros(n)
    weights_hist: dict = {}
    rebal_dates: list = []
    turnover_total = 0.0
    n_rebals = 0

    for d in range(1, n):
        port_ret[d] = float(np.nansum(w_held * ret[d]))
        if d in rebal and d >= warmup:
            signs = tsmom_signs(price_arr, d, params.lookback_months,
                                params.skip_recent_month, params.month_days)
            win = ret[d - params.vol_lookback_days + 1: d + 1]
            cov, vol = estimate_cov(win, params.trading_days_year)
            w_new = target_weights(signs, vol, cov, sleeve_ids, params)
            # no-trade band vs currently held weights
            band = params.rebal_band
            keep = np.abs(w_new - w_held) < band * np.abs(w_new)
            w_new = np.where(keep, w_held, w_new)
            delta = np.abs(w_new - w_held)
            port_ret[d] -= float(np.sum(delta * cost_frac))
            turnover_total += float(delta.sum())
            n_rebals += 1
            w_held = w_new
            weights_hist[prices.index[d]] = pd.Series(w_held, index=tickers)
            rebal_dates.append(prices.index[d])

    daily = pd.Series(port_ret, index=prices.index, name="ret")
    years = max((prices.index[-1] - prices.index[0]).days / 365.25, 1e-9)
    return {
        "daily_ret": daily,
        "turnover_ann": turnover_total / years,     # two-way annualized
        "weights": weights_hist,
        "rebal_dates": rebal_dates,
        "n_rebals": n_rebals,
    }
