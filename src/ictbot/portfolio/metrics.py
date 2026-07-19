"""Portfolio metrics — Sharpe/Sortino/Calmar/DD/turnover + Probabilistic and
Deflated Sharpe Ratio (Bailey & Lopez de Prado), the trial-count-aware
significance bar. No scipy dependency (normal CDF/inverse-CDF implemented here).
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd

EULER_GAMMA = 0.5772156649015329


def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _norm_ppf(p: float) -> float:
    """Inverse standard-normal CDF (Acklam's rational approximation)."""
    if p <= 0.0:
        return -math.inf
    if p >= 1.0:
        return math.inf
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    dd = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
          3.754408661907416e+00]
    plow, phigh = 0.02425, 1 - 0.02425
    if p < plow:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / \
               ((((dd[0]*q+dd[1])*q+dd[2])*q+dd[3])*q+1)
    if p > phigh:
        q = math.sqrt(-2 * math.log(1 - p))
        return -(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / \
               ((((dd[0]*q+dd[1])*q+dd[2])*q+dd[3])*q+1)
    q = p - 0.5
    r = q * q
    return (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*q / \
           (((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1)


@dataclass
class PortMetrics:
    n: int
    cagr: float
    ann_vol: float
    sharpe: float
    sortino: float
    max_dd_pct: float
    calmar: float
    worst_month: float
    monthly_win_rate: float
    skew: float
    kurtosis: float
    turnover_ann: float


def _skew_kurt(r: np.ndarray):
    mu = r.mean()
    sd = r.std(ddof=0)
    if sd == 0:
        return 0.0, 3.0
    z = (r - mu) / sd
    return float((z ** 3).mean()), float((z ** 4).mean())


def compute_metrics(daily_ret: pd.Series, freq: int = 252,
                    turnover_ann: float = float("nan")) -> PortMetrics:
    r = pd.Series(daily_ret).dropna()
    n = len(r)
    if n == 0 or r.std(ddof=1) == 0:
        return PortMetrics(n, 0, 0, 0, 0, 0, 0, 0, 0, 0, 3, turnover_ann)
    mu, sd = r.mean(), r.std(ddof=1)
    sharpe = mu / sd * math.sqrt(freq)
    downside = r[r < 0].std(ddof=1)
    sortino = mu / downside * math.sqrt(freq) if downside and downside > 0 else float("inf")
    nav = (1 + r).cumprod()
    years = n / freq
    cagr = nav.iloc[-1] ** (1 / years) - 1 if nav.iloc[-1] > 0 else -1.0
    dd = (nav / nav.cummax() - 1).min()
    max_dd_pct = abs(dd) * 100
    calmar = cagr / (abs(dd)) if dd < 0 else float("inf")
    monthly = (1 + r).resample("ME").prod() - 1 if hasattr(r.index, "freq") or True else r
    worst_month = float(monthly.min()) if len(monthly) else 0.0
    win = float((monthly > 0).mean()) if len(monthly) else 0.0
    sk, ku = _skew_kurt(r.to_numpy())
    return PortMetrics(n, cagr, sd * math.sqrt(freq), sharpe, sortino, max_dd_pct,
                       calmar, worst_month, win, sk, ku, turnover_ann)


def probabilistic_sharpe(daily_ret: pd.Series, sr_benchmark_ann: float = 0.0,
                         freq: int = 252) -> float:
    """PSR: probability the true Sharpe exceeds ``sr_benchmark_ann``."""
    r = pd.Series(daily_ret).dropna().to_numpy()
    n = len(r)
    if n < 3 or r.std(ddof=1) == 0:
        return float("nan")
    sr = r.mean() / r.std(ddof=1)                 # per-observation
    sk, ku = _skew_kurt(r)
    sr_star = sr_benchmark_ann / math.sqrt(freq)
    den = math.sqrt(max(1 - sk * sr + ((ku - 1) / 4) * sr ** 2, 1e-12))
    return _norm_cdf((sr - sr_star) * math.sqrt(n - 1) / den)


def deflated_sharpe(daily_ret: pd.Series, n_trials: int,
                    trials_ann_sr_std: float, freq: int = 252) -> float:
    """DSR: PSR against the expected-max Sharpe under ``n_trials`` (the null).

    ``trials_ann_sr_std`` = std of the annualized Sharpes across the trials (the
    dispersion the search explored). Larger n_trials / dispersion -> higher bar.
    """
    if n_trials < 2 or trials_ann_sr_std <= 0:
        return probabilistic_sharpe(daily_ret, 0.0, freq)
    var_obs = (trials_ann_sr_std / math.sqrt(freq)) ** 2
    z1 = _norm_ppf(1 - 1.0 / n_trials)
    z2 = _norm_ppf(1 - 1.0 / (n_trials * math.e))
    sr0_obs = math.sqrt(var_obs) * ((1 - EULER_GAMMA) * z1 + EULER_GAMMA * z2)
    return probabilistic_sharpe(daily_ret, sr0_obs * math.sqrt(freq), freq)
