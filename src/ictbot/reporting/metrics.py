"""Metrics & gates — spec B4 (metrics) and B5 (pass gates).

All results are in R. Net R (``r_net``) is used when the cost model has been
applied, else gross ``r_total``. Expectancy is the single most important number
(B4). The six B5 gates are evaluated on the OOS window, with gate 5 (stability)
comparing OOS PF to IS PF and gate 6 (concentration) using the monthly table.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

NAN = float("nan")

# B5 gate thresholds (fixed by the spec)
G_EXPECTANCY = 0.15
G_PF = 1.3
G_MAX_DD_R = 12.0
G_OOS_TRADES = 30
G_STABILITY_RATIO = 0.6      # OOS PF >= 0.6 x IS PF
G_MONTH_CONCENTRATION = 0.40


def r_values(trades: pd.DataFrame, r_col: str | None = None) -> np.ndarray:
    if r_col is None:
        r_col = "r_net" if "r_net" in trades.columns else "r_total"
    return trades[r_col].to_numpy(dtype=float)


@dataclass
class Metrics:
    n: int
    win_rate: float
    avg_rr: float
    expectancy: float
    profit_factor: float
    max_dd_r: float
    max_dd_pct: float
    longest_loss_streak: int
    trades_per_month: float
    mae_p90_winners: float
    mfe_median: float


def compute_metrics(trades: pd.DataFrame, r_col: str | None = None,
                    risk_pct: float = 0.5, window_days: float | None = None) -> Metrics:
    n = len(trades)
    if n == 0:
        return Metrics(0, NAN, NAN, NAN, NAN, 0.0, 0.0, 0, 0.0, NAN, NAN)
    r = r_values(trades, r_col)
    wins, losses = r[r > 0], r[r < 0]

    win_rate = len(wins) / n
    avg_win = wins.mean() if len(wins) else 0.0
    avg_loss = abs(losses.mean()) if len(losses) else 0.0
    avg_rr = (avg_win / avg_loss if avg_loss > 0
              else float("inf") if avg_win > 0 else NAN)
    expectancy = float(r.mean())

    gp, gl = wins.sum(), abs(losses.sum())
    pf = gp / gl if gl > 0 else float("inf") if gp > 0 else 0.0

    eq = np.cumsum(r)
    dd = np.maximum.accumulate(eq) - eq
    max_dd_r = float(dd.max())
    max_dd_pct = max_dd_r * risk_pct               # each R = risk_pct% of equity

    streak = mx = 0
    for x in r:
        streak = streak + 1 if x < 0 else 0
        mx = max(mx, streak)

    et = pd.to_datetime(trades["entry_time"])
    if window_days is None:
        span_days = max((et.max() - et.min()).days, 1)
        window_days = span_days
    months = max(window_days / 30.44, 1e-6)
    trades_per_month = n / months

    mae_p90 = NAN
    if "mae_r" in trades.columns and len(wins):
        mae_win = np.abs(trades["mae_r"].to_numpy(float)[r > 0])
        mae_p90 = float(np.percentile(mae_win, 90))
    mfe_median = (float(np.median(trades["mfe_r"].to_numpy(float)))
                  if "mfe_r" in trades.columns else NAN)

    return Metrics(n, win_rate, avg_rr, expectancy, pf, max_dd_r, max_dd_pct,
                   mx, trades_per_month, mae_p90, mfe_median)


def monthly_net_r(trades: pd.DataFrame, r_col: str | None = None) -> pd.Series:
    """Net R summed per calendar month (index = Period[M])."""
    if trades.empty:
        return pd.Series(dtype=float)
    r = r_values(trades, r_col)
    et = pd.to_datetime(trades["entry_time"])
    if et.dt.tz is not None:
        et = et.dt.tz_localize(None)
    period = et.dt.to_period("M")
    return pd.Series(r, index=period.values).groupby(level=0).sum().sort_index()


def concentration_frac(monthly: pd.Series) -> float:
    """Largest single month's share of total net R (gate 6). NaN if not profitable."""
    total = monthly.sum()
    if len(monthly) == 0 or total <= 0:
        return NAN
    return float(monthly.max() / total)


@dataclass
class GateResult:
    gate1_expectancy: bool
    gate2_pf: bool
    gate3_max_dd: bool
    gate4_oos_n: bool
    gate5_stability: bool
    gate6_concentration: bool
    passed: bool
    is_pf: float
    oos_pf: float
    concentration: float
    oos: Metrics
    is_: Metrics

    def as_flags(self) -> list[bool]:
        return [self.gate1_expectancy, self.gate2_pf, self.gate3_max_dd,
                self.gate4_oos_n, self.gate5_stability, self.gate6_concentration]


def evaluate_gates(is_trades: pd.DataFrame, oos_trades: pd.DataFrame,
                   risk_pct: float = 0.5, r_col: str | None = None) -> GateResult:
    is_m = compute_metrics(is_trades, r_col, risk_pct)
    oos_m = compute_metrics(oos_trades, r_col, risk_pct)
    monthly = monthly_net_r(oos_trades, r_col)
    conc = concentration_frac(monthly)

    g1 = oos_m.expectancy >= G_EXPECTANCY
    g2 = oos_m.profit_factor >= G_PF
    g3 = oos_m.max_dd_r <= G_MAX_DD_R and oos_m.n > 0
    g4 = oos_m.n >= G_OOS_TRADES
    g5 = np.isfinite(is_m.profit_factor) and oos_m.profit_factor >= G_STABILITY_RATIO * is_m.profit_factor
    g6 = conc <= G_MONTH_CONCENTRATION  # NaN -> False
    return GateResult(
        bool(g1), bool(g2), bool(g3), bool(g4), bool(g5), bool(g6),
        bool(g1 and g2 and g3 and g4 and g5 and g6),
        is_m.profit_factor, oos_m.profit_factor, conc, oos_m, is_m,
    )
