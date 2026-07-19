"""DIVTREND portfolio module — data, signal, sizing, backtester, metrics, DSR."""
import math
from pathlib import Path

import numpy as np
import pandas as pd

from ictbot.config import load_config
from ictbot.portfolio.backtest import month_end_positions, run_divtrend
from ictbot.portfolio.data import (
    SYNTH_SLEEVES,
    load_etf_dir,
    prices_to_returns,
    synthetic_prices,
)
from ictbot.portfolio.metrics import (
    compute_metrics,
    deflated_sharpe,
    probabilistic_sharpe,
    _norm_ppf,
)
from ictbot.portfolio.params import DivtrendParams
from ictbot.portfolio.signal import tsmom_signs
from ictbot.portfolio.sizing import estimate_cov, target_weights

CONFIG = Path(__file__).resolve().parents[1] / "config" / "divtrend_v1.0.yaml"


def _params():
    return DivtrendParams.from_config(load_config(CONFIG))


def test_config_loads():
    p = _params()
    assert p.lookback_months == 12 and p.vol_lookback_days == 60
    assert p.target_vol_port == 0.10 and len(p.ranges) == 4


def test_month_end_positions():
    idx = pd.bdate_range("2020-01-01", "2020-03-31")
    pos = month_end_positions(idx)
    months = pd.PeriodIndex(idx[pos], freq="M")
    assert list(months.astype(str)) == ["2020-01", "2020-02", "2020-03"]


def test_tsmom_signs():
    # 3 instruments: up-trend, down-trend, flat
    n = 300
    arr = np.column_stack([
        np.linspace(100, 200, n),   # up
        np.linspace(200, 100, n),   # down
        np.full(n, 150.0),          # flat
    ])
    s = tsmom_signs(arr, d=299, lookback_months=6, skip_recent_month=0, month_days=21)
    assert s[0] == 1 and s[1] == -1 and s[2] == 0
    # insufficient history -> all zero
    assert np.all(tsmom_signs(arr, d=10, lookback_months=12,
                              skip_recent_month=1, month_days=21) == 0)


def test_sizing_equal_risk_and_vol_target():
    p = _params()
    rng = np.random.default_rng(0)
    # two instruments, one twice as volatile
    win = np.column_stack([rng.normal(0, 0.01, 300), rng.normal(0, 0.02, 300)])
    cov, vol = estimate_cov(win, 252)
    assert vol[1] > vol[0]
    w = target_weights(np.array([1.0, 1.0]), vol, cov, np.array([0, 1]), p)
    # lower-vol instrument gets the larger weight (equal risk)
    assert abs(w[0]) > abs(w[1])
    # realized portfolio vol ~ target (within tolerance)
    sig = math.sqrt(w @ cov @ w)
    assert abs(sig - p.target_vol_port) < 0.02 or sig <= p.target_vol_port + 1e-9


def test_backtest_positive_sharpe_on_trending_synth():
    prices = synthetic_prices(n_days=3500, seed=1, per_sleeve=4, trend=0.5)
    res = run_divtrend(prices, _params(), SYNTH_SLEEVES)
    m = compute_metrics(res["daily_ret"], turnover_ann=res["turnover_ann"])
    # trends are embedded -> TSMOM should extract a positive Sharpe
    assert m.n > 2000
    assert m.sharpe > 0.3
    assert res["n_rebals"] > 100
    assert 0 < m.ann_vol < 0.30            # vol target roughly respected


def test_backtest_near_zero_on_noise():
    # pure random walks (trend=0) -> no momentum edge -> Sharpe near zero
    prices = synthetic_prices(n_days=3500, seed=2, per_sleeve=4, trend=0.0)
    res = run_divtrend(prices, _params(), SYNTH_SLEEVES)
    m = compute_metrics(res["daily_ret"])
    assert abs(m.sharpe) < 0.8             # indistinguishable from zero-ish


def test_metrics_and_dsr():
    idx = pd.bdate_range("2010-01-01", periods=1500)
    rng = np.random.default_rng(3)
    r = pd.Series(rng.normal(0.0004, 0.008, len(idx)), index=idx)   # positive drift
    m = compute_metrics(r, turnover_ann=5.0)
    assert m.sharpe > 0
    psr = probabilistic_sharpe(r, 0.0)
    assert 0.0 <= psr <= 1.0
    # more trials / dispersion -> DSR no larger than PSR-vs-zero
    dsr = deflated_sharpe(r, n_trials=20, trials_ann_sr_std=0.5)
    assert 0.0 <= dsr <= 1.0
    assert dsr <= psr + 1e-9


def test_norm_ppf_roundtrip():
    from ictbot.portfolio.metrics import _norm_cdf
    for x in (-2.0, -0.5, 0.0, 1.0, 2.5):
        assert abs(_norm_ppf(_norm_cdf(x)) - x) < 1e-4


def test_load_etf_dir(tmp_path):
    for tk, base in [("SPY", 100), ("TLT", 50)]:
        rows = ["Date,Open,High,Low,Close,Adj Close,Volume"]
        for i in range(5):
            d = pd.Timestamp("2020-01-01") + pd.Timedelta(days=i)
            px = base + i
            rows.append(f"{d.date()},{px},{px},{px},{px},{px},1000")
        (tmp_path / f"{tk}.csv").write_text("\n".join(rows))
    panel = load_etf_dir(tmp_path)
    assert list(panel.columns) == ["SPY", "TLT"]
    rets = prices_to_returns(panel)
    assert len(rets) == 4
