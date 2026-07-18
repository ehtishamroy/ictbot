"""Backtest harness — glue between data, engine, fills and costs (spec B1-B3).

``backtest`` builds features, runs the state machine with a chosen fill model, and
(optionally) applies the cost model. ``split_is_oos`` performs the chronological
70/30 in-sample / out-of-sample split by DATE (never by shuffling — it is a time
series). The OOS window is meant to be looked at once per version (B3/C4).
"""
from __future__ import annotations

import pandas as pd

from ..engine.features import prepare_features
from ..engine.fills import IntrabarFillModel
from ..engine.params import EngineParams
from ..engine.state_machine import run
from .costs import CostModel, apply_costs


def backtest(
    df5: pd.DataFrame,
    df1h: pd.DataFrame,
    params: EngineParams,
    news=None,
    fill_model=None,
    cost_model: CostModel | None = None,
    df1m: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Run one backtest. If ``df1m`` is given, use 1-minute intrabar fills."""
    if fill_model is None and df1m is not None:
        fill_model = IntrabarFillModel(df1m)
    feats = prepare_features(df5, df1h, params)
    trades = run(feats, params, news=news, fill_model=fill_model)
    if cost_model is not None:
        trades = apply_costs(trades, cost_model)
    return trades


def split_is_oos(
    trades: pd.DataFrame,
    data_start: pd.Timestamp,
    data_end: pd.Timestamp,
    is_frac: float = 0.70,
):
    """Split trades chronologically at ``is_frac`` of the DATA window.

    Returns ``(is_trades, oos_trades, boundary_timestamp)``.
    """
    boundary = data_start + (data_end - data_start) * is_frac
    if trades.empty:
        return trades, trades, boundary
    et = pd.to_datetime(trades["entry_time"])
    is_trades = trades[et < boundary]
    oos_trades = trades[et >= boundary]
    return is_trades, oos_trades, boundary
