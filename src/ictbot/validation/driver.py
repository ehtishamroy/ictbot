"""Full validation driver — chains the whole flow into one call.

data -> backtest -> IS/OOS split -> gates -> (if passed) robustness -> Part F report.

Mirrors the C1->C2->C4 sequence: run once at locked parameters, look at OOS once,
and only run robustness when the gates actually pass.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from ..backtest.costs import CostModel
from ..backtest.harness import backtest, split_is_oos
from ..engine.params import EngineParams
from ..reporting.metrics import GateResult, evaluate_gates
from ..reporting.report import part_f_report
from .robustness import RobustnessResult, run_robustness


@dataclass
class ValidationOutcome:
    trades: pd.DataFrame
    is_trades: pd.DataFrame
    oos_trades: pd.DataFrame
    gates: GateResult
    robustness: RobustnessResult | None
    report: str
    status: str


def full_validation(
    df5: pd.DataFrame,
    df1h: pd.DataFrame,
    params: EngineParams,
    cost_model: CostModel,
    data_start: pd.Timestamp,
    data_end: pd.Timestamp,
    *,
    df1m: pd.DataFrame | None = None,
    news=None,
    version: str = "v1.0",
    data_desc: str = "1m",
    mt5_mode: str = "real ticks",
    costs_desc: str | None = None,
    run_robustness_flag: bool = True,
    r_col: str = "r_net",
) -> ValidationOutcome:
    if costs_desc is None:
        costs_desc = (f"spread={cost_model.spread_pips} "
                      f"commission={cost_model.commission_per_lot_roundturn} "
                      f"slippage={cost_model.slippage_pips} (1.0x)")

    trades = backtest(df5, df1h, params, news=news, cost_model=cost_model, df1m=df1m)
    is_t, oos_t, _ = split_is_oos(trades, data_start, data_end)
    gates = evaluate_gates(is_t, oos_t, risk_pct=params.risk_pct, r_col=r_col)

    robustness = None
    if gates.passed and run_robustness_flag:
        def run_fn(p, cm):
            tr = backtest(df5, df1h, p, news=news, cost_model=cm, df1m=df1m)
            _, o, _ = split_is_oos(tr, data_start, data_end)
            return o
        robustness = run_robustness(params, cost_model, run_fn, r_col=r_col)

    if not gates.passed:
        status = "TESTED-FAIL"
    elif robustness is not None and robustness.passed:
        status = "TESTED-PASS"
    else:
        status = "GATES-PASS / ROBUSTNESS-FAIL"

    report = part_f_report(
        version=version, window=f"{data_start.date()}..{data_end.date()}",
        data_desc=data_desc, mt5_mode=mt5_mode, costs_desc=costs_desc,
        is_trades=is_t, oos_trades=oos_t, gates=gates, r_col=r_col,
        risk_pct=params.risk_pct,
        robustness=(robustness.marks() if robustness else None), status=status,
    )
    return ValidationOutcome(trades, is_t, oos_t, gates, robustness, report, status)
