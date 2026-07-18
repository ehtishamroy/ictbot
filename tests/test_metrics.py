"""Phase 6 — B4 metrics, monthly table, concentration, and the six B5 gates."""
import numpy as np
import pandas as pd

from ictbot.reporting.metrics import (
    compute_metrics,
    concentration_frac,
    evaluate_gates,
    monthly_net_r,
)


def _trades(rs, start="2024-01-01", freq="2D", mae=None, mfe=None):
    et = pd.date_range(start, periods=len(rs), freq=freq, tz="UTC")
    df = pd.DataFrame({"entry_time": et, "r_total": rs})
    if mae is not None:
        df["mae_r"] = mae
    if mfe is not None:
        df["mfe_r"] = mfe
    return df


def test_compute_metrics_known_values():
    df = _trades([1.0, -1.0, 2.0, -0.5], mae=[-0.3, -0.2, -0.5, -0.1],
                 mfe=[1.2, 0.1, 2.5, 0.05])
    m = compute_metrics(df, r_col="r_total", risk_pct=0.5, window_days=30.44)
    assert m.n == 4
    assert m.win_rate == 0.5
    assert abs(m.avg_rr - 2.0) < 1e-9          # 1.5 / 0.75
    assert abs(m.expectancy - 0.375) < 1e-9
    assert abs(m.profit_factor - 2.0) < 1e-9   # 3.0 / 1.5
    assert abs(m.max_dd_r - 1.0) < 1e-9
    assert abs(m.max_dd_pct - 0.5) < 1e-9      # 1.0R x 0.5%
    assert m.longest_loss_streak == 1
    assert abs(m.trades_per_month - 4.0) < 1e-6
    assert 0.3 <= m.mae_p90_winners <= 0.5     # winners' MAE p90 (abs R)
    assert abs(m.mfe_median - 0.65) < 1e-9


def test_pf_infinite_when_no_losers():
    m = compute_metrics(_trades([1.0, 2.0]), r_col="r_total", window_days=30.44)
    assert m.profit_factor == float("inf")


def test_monthly_and_concentration():
    df = _trades([5.0, 3.0, 2.0], start="2024-01-15", freq="30D")  # Jan, Feb, Mar
    monthly = monthly_net_r(df, r_col="r_total")
    assert len(monthly) == 3
    assert abs(concentration_frac(monthly) - 0.5) < 1e-9   # 5 / 10
    # evenly split -> under 40%
    even = pd.Series([3.0, 3.0, 4.0])
    assert abs(concentration_frac(even) - 0.4) < 1e-9


def _even_pattern(n):
    # 3 wins (+1R) then 2 losses (-0.5R) repeating -> pf 3.0, expectancy 0.4
    return [1.0 if i % 5 < 3 else -0.5 for i in range(n)]


def test_gates_pass():
    oos = _trades(_even_pattern(40), start="2024-06-01", freq="3D")   # ~4 months
    is_ = _trades(_even_pattern(20), start="2024-01-01", freq="3D")
    g = evaluate_gates(is_, oos, risk_pct=0.5, r_col="r_total")
    assert g.as_flags() == [True] * 6
    assert g.passed is True


def test_gates_fail_on_expectancy_and_count():
    # few trades, break-even -> gate1 (expectancy) and gate4 (count) fail
    oos = _trades([0.1, -0.1, 0.1, -0.1], start="2024-06-01", freq="3D")
    is_ = _trades(_even_pattern(20), start="2024-01-01", freq="3D")
    g = evaluate_gates(is_, oos, risk_pct=0.5, r_col="r_total")
    assert g.gate4_oos_n is False
    assert g.passed is False
