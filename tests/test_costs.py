"""Phase 5 — cost model (spec B2). Numbers computed by hand from the definitions."""
import pandas as pd

from ictbot.backtest.costs import CostModel, apply_costs

CM = CostModel(spread_pips=0.8, commission_per_lot_roundturn=7.0, slippage_pips=0.3)
RD = 0.00172   # risk distance from the long-trade fixture


def test_cost_r_tp2_no_slippage_on_limits():
    # tp1_hit + TP2 exit: both legs are limits -> only spread + commission
    c = CM.cost_r(RD, tp1_hit=True, exit_reason="TP2")
    # spread 0.00008/0.00172 + commission 7/(0.00172*100000)
    assert abs(c - (0.00008 / RD + 7 / (RD * 100_000))) < 1e-12
    assert abs(c - 0.087209) < 1e-5


def test_cost_r_full_stop_includes_slippage():
    c = CM.cost_r(RD, tp1_hit=False, exit_reason="SL")
    expected = 0.00008 / RD + 0.00003 / RD + 7 / (RD * 100_000)  # market_frac 1.0
    assert abs(c - expected) < 1e-12
    assert abs(c - 0.104651) < 1e-5


def test_cost_stress_multiplier():
    base = CM.cost_r(RD, True, "TP2")
    assert abs(CM.scaled(1.5).cost_r(RD, True, "TP2") - 1.5 * base) < 1e-12


def test_apply_costs_columns_and_net():
    trades = pd.DataFrame({
        "r_total": [1.686], "risk_distance": [RD],
        "tp1_hit": [True], "exit_reason": ["TP2"],
    })
    out = apply_costs(trades, CM)
    assert {"r_gross", "cost_r", "r_net"} <= set(out.columns)
    assert out["r_net"].iloc[0] < out["r_gross"].iloc[0]
    assert abs(out["r_net"].iloc[0] - (1.686 - out["cost_r"].iloc[0])) < 1e-12


def test_apply_costs_empty():
    empty = pd.DataFrame(columns=["r_total", "risk_distance", "tp1_hit", "exit_reason"])
    out = apply_costs(empty, CM)
    assert out.empty and {"r_gross", "cost_r", "r_net"} <= set(out.columns)
