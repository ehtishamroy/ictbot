"""Part F report generator — the paste-back template from the spec.

Produces the exact block the spec asks for after every run: IS/OOS metric rows,
the monthly net-R table, the six gate checkboxes, and the robustness line. The
status is restated every time; performance is only ever reported, never assumed.
"""
from __future__ import annotations

import pandas as pd

from .metrics import GateResult, Metrics, compute_metrics, monthly_net_r


def _f(x, nd=2):
    try:
        if x != x:            # NaN
            return "n/a"
        if x == float("inf"):
            return "inf"
        return f"{x:.{nd}f}"
    except (TypeError, ValueError):
        return str(x)


def _metric_row(tag: str, m: Metrics) -> str:
    return (f"{tag}: trades={m.n}  win%={_f(m.win_rate * 100, 1)}  "
            f"avgRR={_f(m.avg_rr)}  expectancy(R)={_f(m.expectancy)}  "
            f"PF={_f(m.profit_factor)}  maxDD(R)={_f(m.max_dd_r)}  "
            f"streak={m.longest_loss_streak}")


def _checkboxes(gates: GateResult) -> str:
    marks = "".join(f"{i}[{'x' if ok else ' '}] "
                    for i, ok in enumerate(gates.as_flags(), start=1))
    return marks.strip()


def part_f_report(
    version: str,
    window: str,
    data_desc: str,
    mt5_mode: str,
    costs_desc: str,
    is_trades: pd.DataFrame,
    oos_trades: pd.DataFrame,
    gates: GateResult,
    r_col: str | None = None,
    risk_pct: float = 0.5,
    robustness: dict | None = None,
    status: str = "UNTESTED",
    strategy_name: str = "NYAM-SWEEP-FVG",
) -> str:
    is_m = compute_metrics(is_trades, r_col, risk_pct)
    oos_m = compute_metrics(oos_trades, r_col, risk_pct)
    monthly = monthly_net_r(oos_trades, r_col)

    lines = [
        f"Strategy: {strategy_name} {version}   Instrument/Session: EURUSD / NY AM",
        f"Window: {window}   Data: {data_desc}   MT5 mode: {mt5_mode}",
        f"Costs: {costs_desc}",
        "",
        _metric_row("IS ", is_m),
        _metric_row("OOS", oos_m),
        (f"Trades/month = {_f(oos_m.trades_per_month)}        "
         f"MAE p90 (winners) = {_f(oos_m.mae_p90_winners)}        "
         f"MFE median = {_f(oos_m.mfe_median)}"),
        "",
        "Monthly net R table (OOS):",
    ]
    if len(monthly):
        for period, val in monthly.items():
            lines.append(f"  {period}: {_f(val)}")
    else:
        lines.append("  (no OOS trades)")

    verdict = "PASS" if gates.passed else "FAIL"
    lines += [
        "",
        f"Gates: {_checkboxes(gates)}   ->  {verdict}",
    ]
    rb = robustness or {}
    lines.append(
        "Robustness (if gates passed): "
        f"perturb[{_mark(rb.get('perturb'))}] "
        f"cost1.5x[{_mark(rb.get('cost_stress'))}] "
        f"session±15[{_mark(rb.get('session_shift'))}] "
        f"monthly[{_mark(rb.get('monthly'))}]"
    )
    lines += ["", f"Status: {status}. Performance reported against the B5 gates only."]
    return "\n".join(lines)


def _mark(v) -> str:
    if v is None:
        return " "
    return "x" if v else "!"
