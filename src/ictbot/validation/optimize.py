"""C3 IS optimisation — one bounded pass, anti-overfitting rules enforced in code.

* <= 3 parameters at a time, coarse grids of 3-5 values each (B7).
* ``sl_buffer_points`` is NEVER grid-searched — it is set from winners' MAE
  (``suggest_sl_buffer_points``), which is why it is rejected as a grid key here.
* Selection is by expectancy, tie-broken by max drawdown (NOT net profit, which
  rewards over-trading) (C3 step 8).

Runs on IN-SAMPLE data only. ``run_fn_is(params) -> is_trades``.
"""
from __future__ import annotations

import itertools

import numpy as np
import pandas as pd

from ..engine.params import EngineParams
from ..reporting.metrics import compute_metrics
from .perturb import set_param

MAX_GRID_PARAMS = 3
MAX_GRID_VALUES = 5


def optimize_is(params: EngineParams, grids: dict[str, list], run_fn_is,
                r_col: str | None = None, risk_pct: float = 0.5) -> pd.DataFrame:
    """Coarse grid search on IS; return a ranked results table (best first)."""
    if len(grids) > MAX_GRID_PARAMS:
        raise ValueError(f"optimise <= {MAX_GRID_PARAMS} params at a time (B7)")
    if "sl_buffer_points" in grids:
        raise ValueError("sl_buffer_points is set from MAE, never grid-searched (C3/B7)")
    for name, values in grids.items():
        if name not in params.ranges:
            raise KeyError(f"{name!r} is not a free parameter")
        if not (1 <= len(values) <= MAX_GRID_VALUES):
            raise ValueError(f"grid for {name!r} must be 1-{MAX_GRID_VALUES} coarse values")

    names = list(grids.keys())
    rows = []
    for combo in itertools.product(*(grids[n] for n in names)):
        p = params
        for name, val in zip(names, combo):
            p = set_param(p, name, val)
        m = compute_metrics(run_fn_is(p), r_col, risk_pct)
        row = {name: getattr(p, name) for name in names}
        row.update(n=m.n, expectancy=m.expectancy, pf=m.profit_factor,
                   max_dd_r=m.max_dd_r)
        rows.append(row)

    df = pd.DataFrame(rows)
    return df.sort_values(["expectancy", "max_dd_r"], ascending=[False, True],
                          na_position="last").reset_index(drop=True)


def suggest_sl_buffer_points(is_trades: pd.DataFrame, params: EngineParams,
                             r_col: str | None = None) -> int:
    """C3 step 7: SL buffer from the 90th-percentile MAE of WINNING IS trades.

    MAE is stored in R; converted to price via each trade's risk distance, then to
    points, then clamped to the A6 ``sl_buffer_points`` range.
    """
    if is_trades.empty or "mae_r" not in is_trades.columns:
        return int(params.sl_buffer_points)
    r = (is_trades["r_net"] if "r_net" in is_trades.columns
         else is_trades["r_total"]).to_numpy(float)
    win = r > 0
    if not win.any():
        return int(params.sl_buffer_points)
    mae_price = np.abs(is_trades["mae_r"].to_numpy(float)[win]
                       * is_trades["risk_distance"].to_numpy(float)[win])
    p90_points = float(np.percentile(mae_price, 90)) / params.point
    return int(params.clamp_free("sl_buffer_points", round(p90_points)))
