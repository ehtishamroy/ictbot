"""Phase 6 — the Part F report renders the required sections and verdict."""
import pandas as pd

from ictbot.reporting.metrics import evaluate_gates
from ictbot.reporting.report import part_f_report


def _trades(rs, start, freq="3D"):
    et = pd.date_range(start, periods=len(rs), freq=freq, tz="UTC")
    return pd.DataFrame({"entry_time": et, "r_total": rs,
                         "mae_r": [-0.3] * len(rs), "mfe_r": [1.0] * len(rs)})


def _even(n):
    return [1.0 if i % 5 < 3 else -0.5 for i in range(n)]


def test_report_contains_all_sections_pass():
    oos = _trades(_even(40), "2024-06-01")
    is_ = _trades(_even(20), "2024-01-01")
    gates = evaluate_gates(is_, oos, r_col="r_total")
    txt = part_f_report(
        version="v1.0", window="2024-01..2024-09",
        data_desc="1m, Dukascopy", mt5_mode="real ticks",
        costs_desc="spread=0.8 commission=7 slippage=0.3 (1.0x)",
        is_trades=is_, oos_trades=oos, gates=gates, r_col="r_total",
        robustness={"perturb": True, "cost_stress": True,
                    "session_shift": True, "monthly": True},
        status="TESTED-PASS",
    )
    assert "NYAM-SWEEP-FVG v1.0" in txt
    assert "IS :" in txt and "OOS:" in txt
    assert "Monthly net R table" in txt
    assert "-> " in txt and "PASS" in txt
    assert "1[x]" in txt                       # gate 1 checked
    assert "Status: TESTED-PASS" in txt


def test_report_marks_fail():
    oos = _trades([0.05, -0.05, 0.05], "2024-06-01")
    is_ = _trades(_even(20), "2024-01-01")
    gates = evaluate_gates(is_, oos, r_col="r_total")
    txt = part_f_report("v1.0", "w", "1m", "real ticks", "c",
                        is_, oos, gates, r_col="r_total")
    assert "FAIL" in txt
